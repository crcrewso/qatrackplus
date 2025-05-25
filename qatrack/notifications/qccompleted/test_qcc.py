from django.contrib.admin.sites import AdminSite
from django.core import mail
import pytest
from django.urls import reverse
from django.utils import timezone
from django_q.models import Schedule

from qatrack.accounts.tests.utils import create_user
from qatrack.notifications.models import (
    QCCompletedNotice,
    RecipientGroup,
    TestListGroup,
    UnitGroup,
)
from qatrack.notifications.qccompleted import admin, tasks
from qatrack.qa import models, signals
import qatrack.qa.tests.utils as utils


@pytest.fixture
def admin_site():
    """Set up the admin site with QCCompletedAdmin."""
    return admin.QCCompletedAdmin(model=QCCompletedNotice, admin_site=AdminSite())


@pytest.fixture
def admin_client():
    """Set up an admin client."""
    user = create_user(is_superuser=True, uname='user', pwd='pwd')
    client = pytest.lazy_fixture('client')
    client.login(username='user', password='pwd')
    return client


@pytest.fixture
def admin_urls():
    """Return URLs for QCCompletedNotice admin."""
    url_add = reverse(
        'admin:%s_%s_add' % (QCCompletedNotice._meta.app_label, QCCompletedNotice._meta.model_name)
    )
    url_list = reverse(
        'admin:%s_%s_changelist' % (
            QCCompletedNotice._meta.app_label,
            QCCompletedNotice._meta.model_name,
        )
    )
    return {'add': url_add, 'list': url_list}


def test_trim():
    """Test admin.trim function."""
    assert admin.trim("foobarbaz", 5) == "foob…"


def has_error(resp, err):
    """Helper to check for error in response."""
    return any(err in e for err_list in resp.context_data['errors'] for e in err_list)


@pytest.mark.django_db
def test_add_completed_with_follow_up_days(admin_client, admin_urls):
    """If the notification type is not follow up, then follow_up_days should not be set."""
    data = {
        'notification_type': QCCompletedNotice.TOLERANCE,
        'follow_up_days': 2,
    }

    resp = admin_client.post(admin_urls['add'], data=data)
    assert has_error(resp, "Leave 'Follow up days'")


@pytest.mark.django_db
def test_add_follow_up_blank_days(admin_client, admin_urls):
    """If notification type is follow up, then follow_up_days must be set."""
    data = {
        'notification_type': QCCompletedNotice.FOLLOW_UP,
        'follow_up_days': "",
    }
    resp = admin_client.post(admin_urls['add'], data=data)

    assert has_error(resp, "You must set the number of days")


@pytest.mark.django_db
def test_get_notification_type_follow_up(admin_site):
    """Test get_notification_type for follow up notification."""
    n = QCCompletedNotice(pk=1, notification_type=QCCompletedNotice.FOLLOW_UP, follow_up_days=2)
    assert "Follow up notification (after 2 days)" in admin_site.get_notification_type(n)


@pytest.mark.django_db
def test_get_notification_type_completed(admin_site):
    """Test get_notification_type for completed notification."""
    n = QCCompletedNotice(pk=1, notification_type=QCCompletedNotice.TOLERANCE, follow_up_days=2)
    assert "Tolerance" in admin_site.get_notification_type(n)


@pytest.mark.django_db
def test_get_units(admin_site):
    """Test get_units admin method."""
    u = utils.create_unit(name="Test Unit")
    ug = UnitGroup.objects.create(name="UG")
    ug.units.add(u)
    rg = RecipientGroup.objects.create(name="RG")
    n = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        units=ug,
        recipients=rg,
    )
    assert ug.name in admin_site.get_units(n)


@pytest.mark.django_db
def test_get_recipients(admin_site):
    """Test get_recipients admin method."""
    rg = RecipientGroup.objects.create(name="RG")
    n = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=rg,
    )
    assert rg.name in admin_site.get_recipients(n)


@pytest.mark.django_db
def test_get_testlists(admin_site):
    """Test get_testlists admin method."""
    tl = utils.create_test_list(name="TL")
    rg = RecipientGroup.objects.create(name="RG")
    tlg = TestListGroup.objects.create(name="TLG")
    tlg.test_lists.add(tl)
    n = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=rg,
        test_lists=tlg,
    )
    assert tlg.name in admin_site.get_testlists(n)


@pytest.fixture
def qc_email_setup():
    """Set up data for QC completed email tests."""
    # Create test data
    tests = []
    ref = models.Reference(type=models.NUMERICAL, value=100.)
    tol = models.Tolerance(type=models.PERCENT, act_low=-3, tol_low=-2, tol_high=2, act_high=3)
    ref.created_by = utils.create_user()
    tol.created_by = utils.create_user()
    ref.modified_by = utils.create_user()
    tol.modified_by = utils.create_user()
    values = [None, None, 96, 97, 100, 100]

    statuses = [utils.create_status(name="status%d" % x, slug="status%d" % x) for x in range(len(values))]

    test_list = utils.create_test_list()
    for i in range(6):
        test = utils.create_test(name="name%d" % i)
        tests.append(test)
        utils.create_test_list_membership(test_list, test)

    testlist_group = TestListGroup.objects.create(name="test group")
    testlist_group.test_lists.add(test_list)

    unit_test_collection = utils.create_unit_test_collection(test_collection=test_list)

    unit_group = UnitGroup.objects.create(name="test group")
    unit_group.units.add(unit_test_collection.unit)

    # Create a test list instance
    tli = utils.create_test_list_instance(unit_test_collection=unit_test_collection)
    for i, (v, test, status) in enumerate(zip(values, tests, statuses)):
        uti = models.UnitTestInfo.objects.get(test=test, unit=unit_test_collection.unit)
        ti = utils.create_test_instance(tli, unit_test_info=uti, value=v, status=status)
        ti.reference = ref
        ti.tolerance = tol
        if i == 0:
            ti.skipped = True
        if i == 1:
            ti.tolerance = None
            ti.reference = None
        else:
            ti.reference.save()
            ti.tolerance.save()

        ti.save()

    group = models.Group.objects.latest('pk')
    user = models.User.objects.latest('pk')
    user.groups.add(group)
    user.email = "example@example.com"
    user.save()

    recipients = RecipientGroup.objects.create(name="test group")
    recipients.groups.add(group)

    inactive_user = models.User.objects.create_user('inactive', 'inactive@user.com', 'password')
    inactive_user.groups.add(group)
    inactive_user.is_active = False
    inactive_user.save()

    # Delete default schedules to make counting easier
    Schedule.objects.all().delete()
    
    # Clear mail outbox
    mail.outbox.clear()

    return {
        'tests': tests,
        'ref': ref,
        'tol': tol,
        'values': values,
        'statuses': statuses,
        'test_list': test_list,
        'testlist_group': testlist_group,
        'unit_test_collection': unit_test_collection,
        'unit_group': unit_group,
        'test_list_instance': tli,
        'group': group,
        'recipients': recipients,
        'inactive_user': inactive_user,
    }


@pytest.mark.django_db
def test_email_sent(qc_email_setup):
    """Test that email is sent when test list instance is completed."""
    notification = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
    )
    notification.save()
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_email_sent_action_only_test(qc_email_setup):
    """If a test list instance has only a failing test, but an alert is configured for 
    tolerance or action level, a notice should be sent."""
    notification = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
    )
    notification.save()
    qc_email_setup['test_list_instance'].testinstance_set.exclude(pass_fail="action").delete()
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_inactive_not_included(qc_email_setup):
    """Test that inactive users don't receive emails."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
    )
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert qc_email_setup['inactive_user'].email not in mail.outbox[0].recipients()


@pytest.mark.django_db
def test_email_not_sent(qc_email_setup):
    """No failing tests so no email should be sent."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
    )

    qc_email_setup['test_list_instance'].testinstance_set.update(pass_fail=models.OK)
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_email_sent_to_group_for_unit(qc_email_setup):
    """Test that email is sent to a group for a unit."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
        units=qc_email_setup['unit_group'],
    )

    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_email_not_sent_to_group_for_excluded_unit(qc_email_setup):
    """TLI is created on 2nd unit so no one should get an email."""
    utc2 = utils.create_unit_test_collection(test_collection=qc_email_setup['test_list'])
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
        units=qc_email_setup['unit_group'],
    )

    tli = utils.create_test_list_instance(unit_test_collection=utc2)
    for i, (v, test, status) in enumerate(zip(
        qc_email_setup['values'], 
        qc_email_setup['tests'], 
        qc_email_setup['statuses']
    )):
        uti = models.UnitTestInfo.objects.get(test=test, unit=utc2.unit)
        ti = utils.create_test_instance(tli, unit_test_info=uti, value=v, status=status)
        ti.reference = qc_email_setup['ref']
        ti.tolerance = qc_email_setup['tol']
        if i == 0:
            ti.skipped = True
        if i == 1:
            ti.tolerance = None
            ti.reference = None
        else:
            ti.reference.save()
            ti.tolerance.save()
        ti.save()

    signals.testlist_complete.send(sender=None, instance=tli, created=True)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_email_not_sent_to_group_for_unit(qc_email_setup):
    """Main group is not included in notification, only the new group, so only one email
    should be sent to the new user."""
    group2 = utils.create_group(name="group2")
    rg = RecipientGroup.objects.create(name='group2')
    rg.groups.add(group2)
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=rg,
        units=qc_email_setup['unit_group'],
    )
    user2 = utils.create_user(uname="user2")
    user2.email = "user2@example.com"
    user2.save()
    user2.groups.add(group2)
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].recipients() == ['user2@example.com']


@pytest.mark.django_db
def test_email_sent_to_group_and_single_user(qc_email_setup):
    """Main group is not included in notification, only new user, so only one email
    should be sent to the new user."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
    )
    user2 = utils.create_user(uname="user2")
    user2.email = "user2@example.com"
    user2.save()
    qc_email_setup['recipients'].users.add(user2)
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 1
    assert list(sorted(mail.outbox[0].recipients())) == ['example@example.com', 'user2@example.com']


@pytest.mark.django_db
def test_email_sent_for_completion(qc_email_setup):
    """Test that email is sent for completion notification type."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.COMPLETED,
        recipients=qc_email_setup['recipients'],
    )
    
    # Create a TLI with all passing tests
    utc = qc_email_setup['unit_test_collection']
    tli = utils.create_test_list_instance(unit_test_collection=utc)
    for i, (v, test, status) in enumerate(zip(
        qc_email_setup['values'], 
        qc_email_setup['tests'], 
        qc_email_setup['statuses']
    )):
        uti = models.UnitTestInfo.objects.get(test=test, unit=utc.unit)
        ti = utils.create_test_instance(tli, unit_test_info=uti, value=v, status=status)
        ti.reference = qc_email_setup['ref']
        ti.tolerance = qc_email_setup['tol']
        if i == 0:
            ti.skipped = True
        
        # All passing
        ti.tolerance = None
        ti.reference = None
        ti.save()

    signals.testlist_complete.send(sender=None, instance=tli, created=True)
    assert len(mail.outbox) == 1
    assert "list was just completed" in mail.outbox[0].alternatives[0][0]


@pytest.mark.django_db
def test_email_not_sent_for_completion_with_notification_type_tol(qc_email_setup):
    """Test that email is not sent for tolerance notification type when all tests pass."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.TOLERANCE,
        recipients=qc_email_setup['recipients'],
    )
    
    # Create a TLI with all passing tests
    utc = qc_email_setup['unit_test_collection']
    tli = utils.create_test_list_instance(unit_test_collection=utc)
    for i, (v, test, status) in enumerate(zip(
        qc_email_setup['values'], 
        qc_email_setup['tests'], 
        qc_email_setup['statuses']
    )):
        uti = models.UnitTestInfo.objects.get(test=test, unit=utc.unit)
        ti = utils.create_test_instance(tli, unit_test_info=uti, value=v, status=status)
        ti.reference = qc_email_setup['ref']
        ti.tolerance = qc_email_setup['tol']
        if i == 0:
            ti.skipped = True
            
        # All passing
        ti.tolerance = None
        ti.reference = None
        ti.save()

    signals.testlist_complete.send(sender=None, instance=tli, created=True)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_email_not_sent_for_diff_testlist(qc_email_setup):
    """Test that email is not sent for a different test list."""
    new_test_list = utils.create_test_list()
    test = utils.create_test(name="new tl name")
    utils.create_test_list_membership(new_test_list, test)
    utc = utils.create_unit_test_collection(
        unit=qc_email_setup['unit_test_collection'].unit, 
        test_collection=new_test_list
    )

    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.COMPLETED,
        recipients=qc_email_setup['recipients'],
        test_lists=qc_email_setup['testlist_group'],
    )
    tli = utils.create_test_list_instance(unit_test_collection=utc)
    uti = utils.create_unit_test_info(unit=utc.unit, test=test)
    utils.create_test_instance(tli, unit_test_info=uti)

    signals.testlist_complete.send(sender=None, instance=tli, created=True)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_email_sent_for_specific_testlist(qc_email_setup):
    """Test that email is sent for a specific test list."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.COMPLETED,
        test_lists=qc_email_setup['testlist_group'],
        recipients=qc_email_setup['recipients'],
    )
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_email_not_sent_for_same_testlist_different_unit(qc_email_setup):
    """Test that email is not sent for the same test list on a different unit."""
    unit = utils.create_unit()
    utc = utils.create_unit_test_collection(unit=unit, test_collection=qc_email_setup['test_list'])
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.COMPLETED,
        test_lists=qc_email_setup['testlist_group'],
        units=qc_email_setup['unit_group'],
        recipients=qc_email_setup['recipients'],
    )

    tli = utils.create_test_list_instance(unit_test_collection=utc)
    for i, (v, test, status) in enumerate(zip(
        qc_email_setup['values'], 
        qc_email_setup['tests'], 
        qc_email_setup['statuses']
    )):
        uti = models.UnitTestInfo.objects.get(test=test, unit=utc.unit)
        ti = utils.create_test_instance(tli, unit_test_info=uti, value=v, status=status)
        ti.reference = qc_email_setup['ref']
        ti.tolerance = qc_email_setup['tol']
        if i == 0:
            ti.skipped = True
        if i == 1:
            ti.tolerance = None
            ti.reference = None
        else:
            ti.reference.save()
            ti.tolerance.save()
        ti.save()

    signals.testlist_complete.send(sender=None, instance=tli, created=True)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_follow_up_email_scheduled(qc_email_setup):
    """Test that follow-up email is scheduled."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.FOLLOW_UP,
        follow_up_days=1,
        test_lists=qc_email_setup['testlist_group'],
        recipients=qc_email_setup['recipients'],
    )
    assert Schedule.objects.count() == 0
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert Schedule.objects.count() == 1


@pytest.mark.django_db
def test_follow_up_email_tli_deleted(qc_email_setup):
    """Confirm deleting a test list instance removes scheduled follow ups."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.FOLLOW_UP,
        follow_up_days=1,
        test_lists=qc_email_setup['testlist_group'],
        recipients=qc_email_setup['recipients'],
    )
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert Schedule.objects.count() == 1
    qc_email_setup['test_list_instance'].delete()
    assert Schedule.objects.count() == 0


@pytest.mark.django_db
def test_follow_up_email_tli_edited(qc_email_setup):
    """Confirm editing a test list instance doesn't duplicate scheduled follow ups."""
    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.FOLLOW_UP,
        follow_up_days=1,
        test_lists=qc_email_setup['testlist_group'],
        recipients=qc_email_setup['recipients'],
    )
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=True
    )
    assert Schedule.objects.count() == 1
    scheduled = Schedule.objects.first().next_run
    qc_email_setup['test_list_instance'].work_completed += timezone.timedelta(days=1)
    qc_email_setup['test_list_instance'].save()
    signals.testlist_complete.send(
        sender=None, 
        instance=qc_email_setup['test_list_instance'], 
        created=False
    )
    assert Schedule.objects.count() == 1
    assert Schedule.objects.first().next_run == scheduled + timezone.timedelta(days=1)


@pytest.mark.django_db
def test_follow_up_not_sent_for_same_testlist_different_unit(qc_email_setup):
    """Test that follow-up is not sent for the same test list on a different unit."""
    unit = utils.create_unit()
    utc = utils.create_unit_test_collection(unit=unit, test_collection=qc_email_setup['test_list'])

    QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.FOLLOW_UP,
        follow_up_days=1,
        test_lists=qc_email_setup['testlist_group'],
        units=qc_email_setup['unit_group'],
        recipients=qc_email_setup['recipients'],
    )

    tli = utils.create_test_list_instance(unit_test_collection=utc)
    for i, (v, test, status) in enumerate(zip(
        qc_email_setup['values'], 
        qc_email_setup['tests'], 
        qc_email_setup['statuses']
    )):
        uti = models.UnitTestInfo.objects.get(test=test, unit=utc.unit)
        ti = utils.create_test_instance(tli, unit_test_info=uti, value=v, status=status)
        ti.reference = qc_email_setup['ref']
        ti.tolerance = qc_email_setup['tol']
        if i == 0:
            ti.skipped = True
        if i == 1:
            ti.tolerance = None
            ti.reference = None
        else:
            ti.reference.save()
            ti.tolerance.save()
        ti.save()

    signals.testlist_complete.send(sender=None, instance=tli, created=True)
    assert Schedule.objects.count() == 0


@pytest.mark.django_db
def test_send_follow_up_email(qc_email_setup):
    """Test sending a follow-up email."""
    notification = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.FOLLOW_UP,
        follow_up_days=1,
        test_lists=qc_email_setup['testlist_group'],
        units=qc_email_setup['unit_group'],
        recipients=qc_email_setup['recipients'],
    )
    tasks.send_follow_up_email(qc_email_setup['test_list_instance'].id, notification.id)
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_send_follow_up_email_no_notice(qc_email_setup):
    """Test sending a follow-up email with no notice."""
    tasks.send_follow_up_email(qc_email_setup['test_list_instance'].id)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_follow_up_email_no_tli(qc_email_setup):
    """Test sending a follow-up email with no test list instance."""
    notification = QCCompletedNotice.objects.create(
        notification_type=QCCompletedNotice.FOLLOW_UP,
        follow_up_days=1,
        recipients=qc_email_setup['recipients'],
    )
    tasks.send_follow_up_email(notification_id=notification.id)
    assert len(mail.outbox) == 0


def test_qc_completed_notice_model_str():
    """Test QCCompletedNotice.__str__."""
    n = QCCompletedNotice(pk=1, notification_type=QCCompletedNotice.FOLLOW_UP)
    assert str(n) == "<QCCompletedNotice(1, Follow up notification)>"
