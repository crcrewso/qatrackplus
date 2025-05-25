from django.contrib.admin.sites import AdminSite
from django.core import mail
import pytest
from django.utils import timezone
from django_q.models import Schedule
import recurrence

from qatrack.notifications.models import (
    RecipientGroup,
    ServiceEventSchedulingNotice,
    UnitGroup,
)
from qatrack.notifications.service_log_scheduling import admin, tasks
import qatrack.qa.tests.utils as qa_utils
from qatrack.qatrack_core.utils import today_start_end
from qatrack.service_log import models
import qatrack.service_log.tests.utils as utils


@pytest.fixture
def admin_site():
    """Set up the admin site."""
    return admin.ServiceEventSchedulingAdmin(model=ServiceEventSchedulingNotice, admin_site=AdminSite())


def test_clean_missing_future_days_upcoming():
    """Test form validation when future_days is missing for upcoming notification."""
    f = admin.ServiceEventSchedulingNoticeAdminForm()
    f.cleaned_data = {'notification_type': ServiceEventSchedulingNotice.UPCOMING}
    f.clean()
    assert 'future_days' in f.errors


def test_clean_missing_future_days_upcoming_and_due():
    """Test form validation when future_days is missing for upcoming_and_due notification."""
    f = admin.ServiceEventSchedulingNoticeAdminForm()
    f.cleaned_data = {'notification_type': ServiceEventSchedulingNotice.UPCOMING_AND_DUE}
    f.clean()
    assert 'future_days' in f.errors


def test_clean_future_days_not_required():
    """Test form validation when future_days is provided but not required."""
    f = admin.ServiceEventSchedulingNoticeAdminForm()
    f.cleaned_data = {'notification_type': ServiceEventSchedulingNotice.DUE, 'future_days': 10}
    f.clean()
    assert 'future_days' in f.errors


def test_clean_ok():
    """Test form validation when all required fields are provided."""
    f = admin.ServiceEventSchedulingNoticeAdminForm()
    f.cleaned_data = {'notification_type': ServiceEventSchedulingNotice.UPCOMING_AND_DUE, 'future_days': 10}
    f.clean()
    assert not f.errors


@pytest.mark.django_db
def test_get_notification_type_upcoming(admin_site):
    """Test get_notification_type for upcoming notification."""
    rg = RecipientGroup.objects.create(name="RG")
    n = ServiceEventSchedulingNotice.objects.create(
        notification_type=ServiceEventSchedulingNotice.UPCOMING,
        future_days=1,
        time="0:00",
        recipients=rg,
    )
    assert "Upcoming Due Dates Only" in admin_site.get_notification_type(n)


@pytest.mark.django_db
def test_get_notification_type_upcoming_and_due(admin_site):
    """Test get_notification_type for upcoming_and_due notification."""
    rg = RecipientGroup.objects.create(name="RG")
    n = ServiceEventSchedulingNotice.objects.create(
        notification_type=ServiceEventSchedulingNotice.UPCOMING_AND_DUE,
        future_days=1,
        time="0:00",
        recipients=rg,
    )
    assert (
        "Notify About Scheduled Service Events Currently Due & Overdue, and Upcoming"
        in admin_site.get_notification_type(n)
    )


@pytest.mark.django_db
def test_get_notification_type_due(admin_site):
    """Test get_notification_type for due notification."""
    rg = RecipientGroup.objects.create(name="RG")
    n = ServiceEventSchedulingNotice.objects.create(
        notification_type=ServiceEventSchedulingNotice.DUE,
        time="0:00",
        recipients=rg,
    )
    assert n.get_notification_type_display() in admin_site.get_notification_type(n)


@pytest.mark.django_db
def test_get_units(admin_site):
    """Test get_units admin method."""
    u = qa_utils.create_unit(name="Test Unit")
    ug = UnitGroup.objects.create(name="UG")
    ug.units.add(u)
    rg = RecipientGroup.objects.create(name="RG")
    n = ServiceEventSchedulingNotice.objects.create(
        notification_type=ServiceEventSchedulingNotice.DUE,
        units=ug,
        recipients=rg,
        time="0:00",
    )
    assert ug.name in admin_site.get_units(n)


@pytest.mark.django_db
def test_get_recipients(admin_site):
    """Test get_recipients admin method."""
    rg = RecipientGroup.objects.create(name="RG")
    n = ServiceEventSchedulingNotice.objects.create(
        notification_type=ServiceEventSchedulingNotice.DUE,
        recipients=rg,
        time="0:00",
    )
    assert rg.name in admin_site.get_recipients(n)


@pytest.fixture
def service_event_model_setup():
    """Set up data for ServiceEventSchedulingModel tests."""
    usa1 = utils.create_unit_service_area()
    usa2 = utils.create_unit_service_area()
    sch1 = utils.create_service_event_schedule(unit_service_area=usa1)
    sch2 = utils.create_service_event_schedule(unit_service_area=usa2)

    unit_group = UnitGroup.objects.create(name="test group")
    unit_group.units.add(usa1.unit)

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

    # Delete defaults schedules to make counting easier
    Schedule.objects.all().delete()

    return {
        'usa1': usa1,
        'usa2': usa2,
        'sch1': sch1,
        'sch2': sch2,
        'unit_group': unit_group,
        'group': group,
        'recipients': recipients,
        'inactive_user': inactive_user,
    }


@pytest.mark.django_db
def test_upcoming_both_overdue_no_groups(service_event_model_setup):
    """Test schedules_to_notify for upcoming with both schedules in window."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    sch1.due_date = timezone.now() + timezone.timedelta(hours=24)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        future_days=7,
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.UPCOMING,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1, sch2]


@pytest.mark.django_db
def test_inactive_not_included(service_event_model_setup):
    """Test schedules_to_notify excludes inactive schedules."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    sch1.due_date = timezone.now() + timezone.timedelta(hours=24)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.active = False
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        future_days=7,
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.UPCOMING,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1]


@pytest.mark.django_db
def test_inactive_unit_not_included(service_event_model_setup):
    """Test schedules_to_notify excludes schedules with inactive units."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    sch1.due_date = timezone.now() + timezone.timedelta(hours=24)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.unit_service_area.unit.active = False
    sch2.unit_service_area.unit.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        future_days=7,
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.UPCOMING,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1]


@pytest.mark.django_db
def test_upcoming_one_overdue_no_groups(service_event_model_setup):
    """Test schedules_to_notify for upcoming with one schedule in window."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    sch1.due_date = timezone.now() + timezone.timedelta(hours=24)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        future_days=1,
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.UPCOMING,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1]


@pytest.mark.django_db
def test_upcoming_both_overdue_unit_group(service_event_model_setup):
    """Test schedules_to_notify for upcoming with unit group filter."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']
    unit_group = service_event_model_setup['unit_group']

    sch1.due_date = timezone.now() + timezone.timedelta(hours=24)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        future_days=7,
        recipients=recipients,
        units=unit_group,
        notification_type=ServiceEventSchedulingNotice.UPCOMING,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1]


@pytest.mark.django_db
def test_all(service_event_model_setup):
    """Test schedules_to_notify for all notification type."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    start, end = today_start_end()
    sch1.due_date = start + timezone.timedelta(hours=12)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.ALL,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1, sch2]


@pytest.mark.django_db
def test_due(service_event_model_setup):
    """Test schedules_to_notify for due notification type."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    start, end = today_start_end()
    sch1.due_date = start + timezone.timedelta(hours=12)
    sch1.save()
    sch2.due_date = timezone.now() + timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.DUE,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1]


@pytest.mark.django_db
def test_due_and_overdue(service_event_model_setup):
    """Test schedules_to_notify for due notification type with overdue schedule."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    start, end = today_start_end()
    sch1.due_date = start + timezone.timedelta(hours=12)
    sch1.save()
    sch2.due_date = timezone.now() - timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.DUE,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1, sch2]


@pytest.mark.django_db
def test_upcoming_and_overdue(service_event_model_setup):
    """Test schedules_to_notify for upcoming_and_due notification type."""
    sch1 = service_event_model_setup['sch1']
    sch2 = service_event_model_setup['sch2']
    recipients = service_event_model_setup['recipients']

    start, end = today_start_end()
    sch1.due_date = start + timezone.timedelta(hours=36)
    sch1.save()
    sch2.due_date = timezone.now() - timezone.timedelta(hours=2 * 24)
    sch2.save()

    notice = ServiceEventSchedulingNotice.objects.create(
        recipients=recipients,
        notification_type=ServiceEventSchedulingNotice.UPCOMING_AND_DUE,
        future_days=7,
        time="0:00",
    )
    assert list(notice.schedules_to_notify()) == [sch1, sch2]


def test_is_props():
    """Test is_* properties of ServiceEventSchedulingNotice."""
    assert ServiceEventSchedulingNotice(notification_type=ServiceEventSchedulingNotice.ALL).is_all
    assert ServiceEventSchedulingNotice(notification_type=ServiceEventSchedulingNotice.DUE).is_due
    assert ServiceEventSchedulingNotice(notification_type=ServiceEventSchedulingNotice.UPCOMING).is_upcoming
    assert ServiceEventSchedulingNotice(
        notification_type=ServiceEventSchedulingNotice.UPCOMING_AND_DUE
    ).is_upcoming_and_due


@pytest.fixture
def service_event_email_setup():
    """Set up data for ServiceEventSchedulingEmails tests."""
    usa1 = utils.create_unit_service_area()
    usa2 = utils.create_unit_service_area()
    sch1 = utils.create_service_event_schedule(unit_service_area=usa1)
    sch2 = utils.create_service_event_schedule(unit_service_area=usa2)

    unit_group = UnitGroup.objects.create(name="test group")
    unit_group.units.add(usa1.unit)

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

    notice = ServiceEventSchedulingNotice.objects.create(
        recipients=recipients,
        recurrences="RRULE:FREQ=DAILY",
        notification_type=ServiceEventSchedulingNotice.UPCOMING_AND_DUE,
        future_days=7,
        time="0:00",
    )
    
    # Delete defaults schedules to make counting easier
    Schedule.objects.all().delete()
    
    # Clear mail outbox
    mail.outbox.clear()

    return {
        'usa1': usa1,
        'usa2': usa2,
        'sch1': sch1,
        'sch2': sch2,
        'unit_group': unit_group,
        'group': group,
        'recipients': recipients,
        'inactive_user': inactive_user,
        'notice': notice,
    }


@pytest.mark.django_db
def test_send_notice(service_event_email_setup):
    """Test send_scheduling_notice with a schedule due now."""
    now = timezone.now()
    service_event_email_setup['sch2'].due_date = timezone.now()
    service_event_email_setup['sch2'].save()
    tasks.send_scheduling_notice(service_event_email_setup['notice'].pk)
    service_event_email_setup['notice'].refresh_from_db()
    assert service_event_email_setup['notice'].last_sent >= now
    assert "QATrack+ Service Event Scheduling Notice:" in mail.outbox[0].subject


@pytest.mark.django_db
def test_send_notice_send_empty(service_event_email_setup):
    """Test send_scheduling_notice with send_empty=True."""
    now = timezone.now()
    service_event_email_setup['notice'].send_empty = True
    service_event_email_setup['notice'].save()
    tasks.send_scheduling_notice(service_event_email_setup['notice'].pk)
    service_event_email_setup['notice'].refresh_from_db()
    assert service_event_email_setup['notice'].last_sent >= now
    assert "QATrack+ Service Event Scheduling Notice:" in mail.outbox[0].subject


@pytest.mark.django_db
def test_send_notice_no_send_empty(service_event_email_setup):
    """Test send_scheduling_notice with no schedules and send_empty=False."""
    tasks.send_scheduling_notice(service_event_email_setup['notice'].pk)
    service_event_email_setup['notice'].refresh_from_db()
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_notice_non_existent(service_event_email_setup):
    """Test send_scheduling_notice with non-existent notice."""
    tasks.send_scheduling_notice(service_event_email_setup['notice'].pk + 1)
    service_event_email_setup['notice'].refresh_from_db()
    assert service_event_email_setup['notice'].last_sent is None
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_notice_no_recipients(service_event_email_setup):
    """Test send_scheduling_notice with no recipients."""
    utils.create_service_event_schedule()
    service_event_email_setup['recipients'].groups.clear()
    service_event_email_setup['notice'].send_empty = True
    service_event_email_setup['notice'].save()
    tasks.send_scheduling_notice(service_event_email_setup['notice'].pk)
    service_event_email_setup['notice'].refresh_from_db()
    assert service_event_email_setup['notice'].last_sent is None
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_schedule_notice(service_event_email_setup):
    """Test schedule_service_event_scheduling_notice."""
    next_run = timezone.now() + timezone.timedelta(hours=1)
    tasks.schedule_service_event_scheduling_notice(service_event_email_setup['notice'], next_run)
    assert Schedule.objects.count() == 1


@pytest.mark.django_db
def test_run_scheduling_notices(service_event_email_setup):
    """Test run_scheduling_notices."""
    service_event_email_setup['notice'].time = (timezone.localtime(timezone.now()) + timezone.timedelta(minutes=1)).time()
    service_event_email_setup['notice'].save()
    tasks.run_scheduling_notices()
    assert Schedule.objects.count() == 1
