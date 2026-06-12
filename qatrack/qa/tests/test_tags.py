from unittest import mock

import pytest
from django.conf import settings
from django.utils import timezone
import recurrence

from qatrack.qa import models
from qatrack.qa.templatetags import qa_tags
from qatrack.qa.views import forms

from . import utils


@pytest.fixture
def unit_test_list():
    """Fixture for creating a unit test collection."""
    return utils.create_unit_test_collection()


@pytest.mark.django_db
def test_qa_value_form(unit_test_list):
    """Test that qa_value_form tag returns valid string."""
    form = forms.CreateTestInstanceForm()
    perms = {
        'qa': {
            'can_view_history': False,
            'can_view_ref_tol': False,
        }
    }
    user = None
    rendered = qa_tags.qa_value_form(form, unit_test_list.tests_object, perms, user)
    assert isinstance(rendered, str)


@pytest.mark.django_db
def test_due_date(unit_test_list):
    """Test that as_due_date tag returns valid string."""
    rendered = qa_tags.as_due_date(unit_test_list)
    assert isinstance(rendered, str)


@pytest.mark.django_db
def test_as_pass_fail_status(unit_test_list):
    """Test that as_pass_fail_status tag returns valid string."""
    tli = utils.create_test_list_instance(
        unit_test_collection=unit_test_list
    )
    rendered = qa_tags.as_pass_fail_status(tli)
    assert isinstance(rendered, str)


@pytest.mark.django_db
def test_as_data_attributes(unit_test_list):
    """Test that as_data_attributes tag returns valid string."""
    rendered = qa_tags.as_data_attributes(unit_test_list)
    assert isinstance(rendered, str)


@pytest.mark.django_db
def test_as_review_status(unit_test_list):
    """Test that as_review_status tag returns valid string."""
    tli = utils.create_test_list_instance(unit_test_collection=unit_test_list)
    uti = utils.create_unit_test_info(unit=unit_test_list.unit, assigned_to=unit_test_list.assigned_to)
    ti = utils.create_test_instance(tli, unit_test_info=uti)
    ti.comment = "test"
    ti.test_list_instance = tli
    tli.comment = "comment"
    ti.save()
    qa_tags.as_review_status(tli)


def test_no_ref():
    """Test reference_tolerance_span with no reference."""
    t = models.Test(type=models.BOOLEAN)
    assert "No Ref" in qa_tags.reference_tolerance_span(t, None, None)


def test_no_ref_no_tol():
    """Test reference_tolerance_span with no reference and no tolerance."""
    t = models.Test(type=models.MULTIPLE_CHOICE)
    assert "No Tol" in qa_tags.reference_tolerance_span(t, None, None)


def test_bool():
    """Test reference_tolerance_span with boolean test type."""
    t = models.Test(type=models.BOOLEAN)
    r = models.Reference(value=1)
    assert "Passing value" in qa_tags.reference_tolerance_span(t, r, None)


def test_no_tol():
    """Test reference_tolerance_span with no tolerance."""
    t = models.Test(type=models.NUMERICAL)
    r = models.Reference(value=1)
    result = qa_tags.reference_tolerance_span(t, r, None)
    assert "No Tolerance" in result


def test_multiple_choice():
    """Test reference_tolerance_span with multiple choice test type."""
    t = models.Test(type=models.MULTIPLE_CHOICE, choices="foo,bar,baz")
    tol = models.Tolerance(type=models.MULTIPLE_CHOICE, mc_tol_choices="foo", mc_pass_choices="")
    result = qa_tags.reference_tolerance_span(t, None, tol)
    assert "Tolerance Values" in result


def test_absolute():
    """Test reference_tolerance_span with absolute tolerance type."""
    t = models.Test(type=models.NUMERICAL)
    r = models.Reference(value=1)
    tol = models.Tolerance(
        type=models.ABSOLUTE,
        act_low=-2, tol_low=-1, tol_high=1, act_high=2,
    )
    result = qa_tags.reference_tolerance_span(t, r, tol)
    assert "%s L" % (settings.TEST_STATUS_DISPLAY_SHORT['action']) in result


@pytest.mark.django_db
def test_percent():
    """Test reference_tolerance_span with percent tolerance type."""
    t = models.Test(type=models.NUMERICAL)
    r = models.Reference(value=1)
    tol = utils.create_tolerance(tol_type=models.PERCENT, act_low=-2, tol_low=-1, tol_high=1, act_high=2)
    result = qa_tags.reference_tolerance_span(t, r, tol)
    assert "(-2.00%" in result


def test_tolerance_no_ref():
    """Test tolerance_for_reference with no reference."""
    tol = models.Tolerance(type=models.PERCENT)
    assert "" == qa_tags.tolerance_for_reference(tol, None)


def test_tolerance_bool():
    """Test tolerance_for_reference with boolean reference type."""
    r = models.Reference(value=1, type=models.BOOLEAN)
    assert "%s: Yes" % (settings.TEST_STATUS_DISPLAY['ok']) in qa_tags.tolerance_for_reference(None, r)


def test_tolerance_no_tol():
    """Test tolerance_for_reference with no tolerance."""
    r = models.Reference(value=1)
    assert "N/A" in qa_tags.tolerance_for_reference(None, r)


def test_tolerance_multiple_choice():
    """Test tolerance_for_reference with multiple choice tolerance type."""
    tol = models.Tolerance(type=models.MULTIPLE_CHOICE, mc_tol_choices="foo", mc_pass_choices="")
    assert "%s: foo" % (settings.TEST_STATUS_DISPLAY['tolerance']) in qa_tags.tolerance_for_reference(tol, None)


def test_tolerance_absolute():
    """Test tolerance_for_reference with absolute tolerance type."""
    r = models.Reference(value=1)
    tol = models.Tolerance(
        type=models.ABSOLUTE,
        act_low=-2, tol_low=-1, tol_high=1, act_high=2,
    )
    assert "Between 0 &amp; 2" in qa_tags.tolerance_for_reference(tol, r)


@pytest.fixture
def wed_frequency():
    """Generate a Wed frequency with a 1 day window_start and 1 day window_end."""
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


def test_qc_window_start_and_end(wed_frequency):
    """Test as_qc_window with window start and end."""
    utc = mock.Mock()
    utc.due_date = timezone.datetime(2018, 11, 29, 2, 0, tzinfo=timezone.utc)  # 28th in EST
    utc.frequency = wed_frequency
    window = qa_tags.as_qc_window(utc)
    assert window == "27 Nov 2018 - 29 Nov 2018"


def test_qc_window_no_start():
    """Test as_qc_window with no window_start."""
    utc = mock.Mock()
    utc.due_date = timezone.datetime(2018, 11, 29, 2, 0, tzinfo=timezone.utc)  # 28th in EST
    utc.frequency = utils.create_frequency(name="w", slug="w", interval=7, window_end=4, save=False)
    window = qa_tags.as_qc_window(utc)
    assert window == "28 Nov 2018 - 02 Dec 2018"


def test_qc_window_no_due_date():
    """Test as_qc_window with no due date."""
    utc = mock.Mock()
    utc.due_date = None
    utc.frequency = utils.create_frequency(name="w", slug="w", interval=7, window_end=4, save=False)
    window = qa_tags.as_qc_window(utc)
    assert window == ""
