from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
import recurrence

from qatrack.qa import models
from qatrack.qa.templatetags import qa_tags
from qatrack.qa.views import forms

from . import utils


class TestTags(TestCase):
    """
    These tests are only testing the tags return valid strings and not
    actually testing functionality.
    """

    def setUp(self):
        self.unit_test_list = utils.create_unit_test_collection()

    def test_qa_value_form(self):
        form = forms.CreateTestInstanceForm()
        perms = {
            'qa': {
                'can_view_history': False,
                'can_view_ref_tol': False,
            }
        }
        user = None
        rendered = qa_tags.qa_value_form(form, self.unit_test_list.tests_object, perms, user)
        self.assertIsInstance(rendered, str)

    def test_due_date(self):
        rendered = qa_tags.as_due_date(self.unit_test_list)
        self.assertIsInstance(rendered, str)

    def test_as_pass_fail_status(self):

        tli = utils.create_test_list_instance(
            unit_test_collection=self.unit_test_list
        )
        rendered = qa_tags.as_pass_fail_status(tli)
        self.assertIsInstance(rendered, str)

    def test_as_data_attributes(self):
        rendered = qa_tags.as_data_attributes(self.unit_test_list)
        self.assertIsInstance(rendered, str)

    def test_as_review_status(self):
        tli = utils.create_test_list_instance(unit_test_collection=self.unit_test_list)
        uti = utils.create_unit_test_info(unit=self.unit_test_list.unit, assigned_to=self.unit_test_list.assigned_to)
        ti = utils.create_test_instance(tli, unit_test_info=uti)
        ti.comment = "test"
        ti.test_list_instance = tli
        tli.comment = "comment"
        ti.save()
        qa_tags.as_review_status(tli)

    def test_as_review_status_with_label(self):
        tli = utils.create_test_list_instance()
        status = qa_tags.as_review_status(tli, show_label=True)
        assert tli.review_status.name in status

    def test_as_review_status_no_label_default(self):
        tli = utils.create_test_list_instance()
        status = qa_tags.as_review_status(tli)
        assert tli.review_status.name not in status


class TestRefTolSpan(TestCase):

    def test_no_ref(self):
        t = models.Test(type=models.BOOLEAN)
        self.assertIn("No Ref", qa_tags.reference_tolerance_span(t, None, None))

    def test_no_ref_no_tol(self):
        t = models.Test(type=models.MULTIPLE_CHOICE)
        self.assertIn("No Tol", qa_tags.reference_tolerance_span(t, None, None))

    def test_bool(self):
        t = models.Test(type=models.BOOLEAN)
        r = models.Reference(value=1)
        self.assertIn("Passing value", qa_tags.reference_tolerance_span(t, r, None))

    def test_no_tol(self):
        t = models.Test(type=models.NUMERICAL)
        r = models.Reference(value=1)
        result = qa_tags.reference_tolerance_span(t, r, None)
        self.assertIn("No Tolerance", result)

    def test_multiple_choice(self):
        t = models.Test(type=models.MULTIPLE_CHOICE, choices="foo,bar,baz")
        tol = models.Tolerance(type=models.MULTIPLE_CHOICE, mc_tol_choices="foo", mc_pass_choices="")
        result = qa_tags.reference_tolerance_span(t, None, tol)
        self.assertIn("Tolerance Values", result)

    def test_absolute(self):
        t = models.Test(type=models.NUMERICAL)
        r = models.Reference(value=1)
        tol = models.Tolerance(
            type=models.ABSOLUTE,
            act_low=-2, tol_low=-1, tol_high=1, act_high=2,
        )
        result = qa_tags.reference_tolerance_span(t, r, tol)
        self.assertIn("%s L" % (settings.TEST_STATUS_DISPLAY_SHORT['action']), result)

    def test_percent(self):
        t = models.Test(type=models.NUMERICAL)
        r = models.Reference(value=1)
        tol = utils.create_tolerance(tol_type=models.PERCENT, act_low=-2, tol_low=-1, tol_high=1, act_high=2)
        result = qa_tags.reference_tolerance_span(t, r, tol)
        self.assertIn("(-2.00%", result)


class TestToleranceForReference(TestCase):

    def test_no_ref(self):
        tol = models.Tolerance(type=models.PERCENT)
        self.assertEqual("", qa_tags.tolerance_for_reference(tol, None))

    def test_bool(self):
        r = models.Reference(value=1, type=models.BOOLEAN)
        self.assertIn("%s: Yes" % (settings.TEST_STATUS_DISPLAY['ok']), qa_tags.tolerance_for_reference(None, r))

    def test_no_tol(self):
        r = models.Reference(value=1)
        self.assertIn("N/A", qa_tags.tolerance_for_reference(None, r))

    def test_multiple_choice(self):
        tol = models.Tolerance(type=models.MULTIPLE_CHOICE, mc_tol_choices="foo", mc_pass_choices="")
        assert "%s: foo" % (settings.TEST_STATUS_DISPLAY['tolerance']) in qa_tags.tolerance_for_reference(tol, None)

    def test_absolute(self):
        r = models.Reference(value=1)
        tol = models.Tolerance(
            type=models.ABSOLUTE,
            act_low=-2, tol_low=-1, tol_high=1, act_high=2,
        )

        self.assertIn("Between 0 &amp; 2", qa_tags.tolerance_for_reference(tol, r))


class TestAsQCWindow:

    @property
    def wed(self):
        """Generate a Wed frequency with a 1 day window_start and 1 day window_end"""
        rule = recurrence.Rule(
            freq=recurrence.WEEKLY,
            byday=[recurrence.WE],
        )
        return models.Frequency(
            name="Wed",
            slug="wed",
            recurrences=recurrence.Recurrence(
                rrules=[rule],
                dtstart=timezone.datetime(2012, 1, 1, tzinfo=timezone.utc),
            ),
            window_start=1,
            window_end=1,
        )

    def test_start_and_end(self):
        """Window start and end so should show 1 day before and after due date"""
        utc = mock.Mock()
        utc.due_date = timezone.datetime(2018, 11, 29, 2, 0, tzinfo=timezone.utc)  # 28th in EST
        utc.frequency = self.wed
        window = qa_tags.as_qc_window(utc)
        assert window == "27 Nov 2018 - 29 Nov 2018"

    def test_no_start(self):
        """No window_start so window should show as due date to overdue date"""
        utc = mock.Mock()
        utc.due_date = timezone.datetime(2018, 11, 29, 2, 0, tzinfo=timezone.utc)  # 28th in EST
        utc.frequency = utils.create_frequency(name="w", slug="w", interval=7, window_end=4, save=False)
        window = qa_tags.as_qc_window(utc)
        assert window == "28 Nov 2018 - 02 Dec 2018"

    def test_no_due_date(self):
        """No due date so no window available"""
        utc = mock.Mock()
        utc.due_date = None
        utc.frequency = utils.create_frequency(name="w", slug="w", interval=7, window_end=4, save=False)
        window = qa_tags.as_qc_window(utc)
        assert window == ""
