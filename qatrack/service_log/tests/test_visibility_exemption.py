"""Service event schedules honour the same visibility exemption as QC (aviary B76).

`visible_to` narrowing is a convenience for users in groups, not an
authorisation boundary; a user who holds `qa.can_review_non_visible_tli` -
every superuser - sees every group's schedules, as #883 arranged for test
lists. Two places here still narrowed by `user.groups.all()` alone.
"""

from django.test import RequestFactory, TestCase
from django.urls import reverse

from qatrack.qa.tests import utils as qa_utils
from qatrack.service_log import views
from qatrack.service_log.tests import utils


class VisibilitySetup(TestCase):

    def setUp(self):
        qa_utils.create_status()
        utils.create_service_event_status(is_default=True)
        self.group = qa_utils.create_group()
        self.schedule = utils.create_service_event_schedule()
        self.schedule.visible_to.set([self.group])
        self.superuser = qa_utils.create_user(is_superuser=True)
        self.superuser.groups.clear()
        self.member = qa_utils.create_user(is_superuser=False)
        self.member.groups.set([self.group])


class TestScheduleList(VisibilitySetup):

    def queryset_for(self, user):
        view = views.ServiceEventScheduleList()
        view.request = RequestFactory().get(reverse("se_schedule_list_all"))
        view.request.user = user
        view.kwargs = {}
        return list(view.get_queryset())

    def test_a_superuser_in_no_groups_sees_the_schedule(self):
        assert self.queryset_for(self.superuser) == [self.schedule]

    def test_a_member_sees_the_schedule(self):
        assert self.queryset_for(self.member) == [self.schedule]

    def test_a_plain_user_in_no_groups_does_not(self):
        plain = qa_utils.create_user(is_superuser=False)
        plain.groups.clear()
        plain.user_permissions.clear()  # the factory grants every permission, including the exemption
        assert self.queryset_for(plain) == []


class TestCreateFromSchedule(VisibilitySetup):
    """`?se_schedule=<pk>` on the create page 404ed for a superuser in no groups."""

    def test_a_superuser_in_no_groups_can_start_from_the_schedule(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse("sl_new"), {"se_schedule": self.schedule.pk})
        assert resp.status_code == 200
