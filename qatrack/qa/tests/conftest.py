import io
import pytest
from unittest import mock
from django.utils import timezone
from qatrack.qa import models
from qatrack.qa.tests import utils


@pytest.fixture
def user():
    """Create a user for testing."""
    return utils.create_user()


@pytest.fixture
def test_instance_status():
    """Create a test instance status."""
    valid_status = models.TestInstanceStatus(
        name="valid",
        slug="valid",
        is_default=True,
        requires_review=True,
        valid=True,
    )
    valid_status.save()
    return valid_status


@pytest.fixture
def test_obj():
    """Create a test object."""
    return utils.create_test()


@pytest.fixture
def test_list():
    """Create a test list."""
    return utils.create_test_list()


@pytest.fixture
def test_list_membership(test_list, test_obj):
    """Create a test list membership."""
    return utils.create_test_list_membership(test_list=test_list, test=test_obj)


@pytest.fixture
def daily_frequency():
    """Create a daily frequency."""
    return utils.create_frequency(name="daily", slug="daily", interval=1, window_end=0)


@pytest.fixture
def monthly_frequency():
    """Create a monthly frequency."""
    return utils.create_frequency(name="monthly", slug="monthly", interval=28, window_end=7)


@pytest.fixture
def unit():
    """Create a unit."""
    return utils.create_unit()


@pytest.fixture
def unit_test_collection(test_list, daily_frequency):
    """Create a unit test collection."""
    return utils.create_unit_test_collection(test_collection=test_list, frequency=daily_frequency)


@pytest.fixture
def unit_test_info(unit, test_obj):
    """Create a unit test info."""
    return utils.create_unit_test_info(unit=unit, test=test_obj)


@pytest.fixture
def test_list_instance(unit_test_collection):
    """Create a test list instance."""
    return utils.create_test_list_instance(unit_test_collection=unit_test_collection)


@pytest.fixture
def test_instance(test_list_instance, unit_test_info):
    """Create a test instance."""
    return utils.create_test_instance(
        test_list_instance=test_list_instance,
        unit_test_info=unit_test_info
    )


@pytest.fixture
def test_cycle(test_list):
    """Create a test cycle."""
    return utils.create_cycle([test_list])


@pytest.fixture
def mock_attachment():
    """Create a mock attachment."""
    mocka = mock.Mock()
    mocka.path = "/tmp/foo.bar"
    mocka.name = "foo.bar"
    return mocka


@pytest.fixture
def string_io():
    """Create a StringIO object."""
    return io.StringIO()