"""Reproductions of user-reported API issues, each named for its upstream issue.

Every test here was written to fail on 4.0.2 (`e0936698`) before its fix landed.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from qatrack.qa import models
from qatrack.qa.tests import utils


class ReportedIssuesSetup(APITestCase):

    def setUp(self):
        utils.create_status()
        self.unit = utils.create_unit()
        self.test_list = utils.create_test_list("test list")
        self.t1 = utils.create_test(name="test1")
        self.t2 = utils.create_test(name="test2")
        self.t3 = utils.create_test(name="test3", test_type=models.STRING)
        for order, t in enumerate([self.t1, self.t2, self.t3]):
            utils.create_test_list_membership(self.test_list, t, order=order)

        self.utc = utils.create_unit_test_collection(
            test_collection=self.test_list,
            unit=self.unit,
            frequency=utils.create_frequency(name="daily"),
        )
        self.create_url = reverse('testlistinstance-list')
        self.utc_url = reverse("unittestcollection-detail", kwargs={'pk': self.utc.pk})

        user = utils.create_user(is_superuser=True)
        self.client.force_authenticate(user=user)

        self.data = {
            'unit_test_collection': self.utc_url,
            'work_completed': '2026-10-25 10:49:47',
            'work_started': '2026-10-25 10:49:00',
            'tests': {
                'test1': {'value': 1},
                'test2': {'value': 2},
                'test3': {'value': "three"},
            },
        }


class TestIssue661InProgressBlanks(ReportedIssuesSetup):
    """#661: the API forced every unfinished test to be skipped on an in-progress
    session, where the perform page accepts blanks."""

    def test_in_progress_accepts_missing_tests(self):
        del self.data['tests']['test2']
        del self.data['tests']['test3']
        self.data['in_progress'] = True

        resp = self.client.post(self.create_url, self.data, format='json')

        assert resp.status_code == 201, resp.data
        tli = models.TestListInstance.objects.get()
        assert tli.in_progress
        blank = tli.testinstance_set.get(unit_test_info__test=self.t2)
        assert blank.value is None
        assert not blank.skipped
        blank_string = tli.testinstance_set.get(unit_test_info__test=self.t3)
        assert blank_string.string_value == ""

    def test_in_progress_accepts_explicit_blank(self):
        self.data['tests']['test2'] = {'value': None}
        self.data['in_progress'] = True

        resp = self.client.post(self.create_url, self.data, format='json')

        assert resp.status_code == 201, resp.data
        assert models.TestListInstance.objects.get().testinstance_set.get(unit_test_info__test=self.t2).value is None

    def test_completed_session_still_requires_every_test(self):
        del self.data['tests']['test2']

        resp = self.client.post(self.create_url, self.data, format='json')

        assert resp.status_code == 400
        assert "Missing data for tests: test2" in str(resp.data)


class TestIssue808CycleDay(ReportedIssuesSetup):
    """#808: META['cycle_day'] was 0-indexed through the API and 1-indexed on the
    perform page, so a procedure that keys on it picked a different item."""

    def test_meta_cycle_day_matches_the_perform_page(self):
        tc = utils.create_test(name="which_day", test_type=models.COMPOSITE)
        tc.calculation_procedure = "result = META['cycle_day']"
        tc.save()
        utils.create_test_list_membership(self.test_list, tc, order=3)

        resp = self.client.post(self.create_url, self.data, format='json')

        assert resp.status_code == 201, resp.data
        ti = models.TestListInstance.objects.get().testinstance_set.get(unit_test_info__test=tc)
        # The perform page shows day 1 for the first (only) day of a plain test
        # list, and perform.py stores it as day 0; the API must present the
        # same number to the procedure.
        assert ti.value == 1
        assert models.TestListInstance.objects.get().day == 0
