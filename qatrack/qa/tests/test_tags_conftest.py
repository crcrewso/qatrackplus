import pytest
from unittest import mock

from django.utils import timezone
import recurrence

from qatrack.qa import models
from qatrack.qa.tests import utils


@pytest.fixture
def unit_test_list():
    """Create a unit test list collection."""
    return utils.create_unit_test_collection()


@pytest.fixture
def test_list_instance(unit_test_list):
    """Create a test list instance with unit_test_collection."""
    return utils.create_test_list_instance(unit_test_collection=unit_test_list)


@pytest.fixture
def unit_test_info(unit_test_list):
    """Create a unit test info for test tags."""
    return utils.create_unit_test_info(
        unit=unit_test_list.unit, 
        assigned_to=unit_test_list.assigned_to
    )


@pytest.fixture
def test_instance_with_comments(test_list_instance, unit_test_info):
    """Create a test instance with comments."""
    ti = utils.create_test_instance(test_list_instance, unit_test_info=unit_test_info)
    ti.comment = "test"
    ti.test_list_instance = test_list_instance
    test_list_instance.comment = "comment"
    ti.save()
    return ti


@pytest.fixture
def test_numerical():
    """Create a numerical test."""
    return models.Test(type=models.NUMERICAL)


@pytest.fixture
def test_boolean():
    """Create a boolean test."""
    return models.Test(type=models.BOOLEAN)


@pytest.fixture
def test_multiple_choice():
    """Create a multiple choice test."""
    return models.Test(type=models.MULTIPLE_CHOICE, choices="foo,bar,baz")


@pytest.fixture
def reference_numerical():
    """Create a numerical reference."""
    return models.Reference(value=1)


@pytest.fixture
def reference_boolean():
    """Create a boolean reference."""
    return models.Reference(value=1, type=models.BOOLEAN)


@pytest.fixture
def tolerance_absolute():
    """Create an absolute tolerance."""
    return models.Tolerance(
        type=models.ABSOLUTE,
        act_low=-2, tol_low=-1, tol_high=1, act_high=2,
    )


@pytest.fixture
def tolerance_percent():
    """Create a percent tolerance."""
    return utils.create_tolerance(
        tol_type=models.PERCENT, 
        act_low=-2, tol_low=-1, tol_high=1, act_high=2
    )


@pytest.fixture
def tolerance_multiple_choice():
    """Create a multiple choice tolerance."""
    return models.Tolerance(
        type=models.MULTIPLE_CHOICE, 
        mc_tol_choices="foo", 
        mc_pass_choices=""
    )


@pytest.fixture
def wednesday_frequency():
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


@pytest.fixture
def mock_utc_with_due_date():
    """Create a mock UTC with due date."""
    utc = mock.Mock()
    utc.due_date = timezone.datetime(2018, 11, 29, 2, 0, tzinfo=timezone.utc)  # 28th in EST
    return utc