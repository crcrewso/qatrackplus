from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from qatrack.qa import models
from qatrack.qa.tests import utils


class TestTestListInstanceAPIPermissions(APITestCase):

    def setUp(self):
        self.unit = utils.create_unit()
        self.test_list = utils.create_test_list("test list")
        self.t1 = utils.create_test(name="test1")
        self.t2 = utils.create_test(name="test2")
        self.t3 = utils.create_test(name="test3", test_type=models.STRING)
        self.t4 = utils.create_test(name="test4", test_type=models.BOOLEAN)
        self.t5 = utils.create_test(name="test5", test_type=models.MULTIPLE_CHOICE, choices="choice1,choice2")

        self.default_tests = [self.t1, self.t2, self.t3, self.t4, self.t5]
        for order, test in enumerate(self.default_tests):
            utils.create_test_list_membership(self.test_list, test, order=order)

        frequency = utils.create_frequency(name="daily")
        self.utc = utils.create_unit_test_collection(
            test_collection=self.test_list, unit=self.unit, frequency=frequency
        )

        self.create_url = reverse("testlistinstance-list")
        self.data = {
            "unit_test_collection": reverse("unittestcollection-detail", kwargs={"pk": self.utc.pk}),
            "work_completed": "2019-07-25 10:49:47",
            "work_started": "2019-07-25 10:49:00",
            "tests": {
                "test1": {"value": 1},
                "test2": {"value": 2},
                "test3": {"value": "test three"},
                "test4": {"value": True},
                "test5": {"value": "choice2"},
            },
        }

        self.client.login(username="user", password="password")
        utils.create_status()

    # Previous test name: test_edit_perms
    def test_user_with_change_permission_can_edit_testlistinstance(self):
        """Refactored from the monolithic API suite into a permission-focused file."""

        response = self.client.post(self.create_url, self.data)
        self.client.logout()

        user = utils.create_user(uname="user2", is_staff=False, is_superuser=False)
        user.user_permissions.add(Permission.objects.get(codename="change_testlistinstance"))
        self.client.force_authenticate(user=user)

        payload = {'tests': {'test1': {'value': 99}}}
        edit_response = self.client.patch(response.data['url'], payload)

        assert edit_response.status_code == 200

    # Previous test name: test_no_edit_perms
    def test_user_without_change_permission_cannot_edit_testlistinstance(self):
        """Refactored from the monolithic API suite into a permission-focused file."""

        response = self.client.post(self.create_url, self.data)
        self.client.logout()

        user = utils.create_user(uname="user2", is_staff=False, is_superuser=False)
        self.client.force_authenticate(user=user)

        payload = {'tests': {'test1': {'value': 99}}}
        edit_response = self.client.patch(response.data['url'], payload)

        assert edit_response.status_code == 403
