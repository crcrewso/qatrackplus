import pytest
from django.utils import timezone
import pytz

from qatrack.qa.models import Frequency, TestListInstance
from qatrack.qa.tests import utils
from qatrack.reports import qc
from qatrack.units.models import Site as USite


@pytest.fixture
def site():
    """Create a test site."""
    return USite.objects.create(name="site")


@pytest.fixture
def unit(site):
    """Create a test unit with site."""
    return utils.create_unit(site=site)


@pytest.fixture
def unit_without_site():
    """Create a test unit without site."""
    return utils.create_unit(site=None)


@pytest.fixture
def unit_test_collection(unit):
    """Create a unit test collection with unit."""
    return utils.create_unit_test_collection(unit=unit)


@pytest.fixture
def unit_test_collection2(unit_without_site):
    """Create a unit test collection with unit2."""
    return utils.create_unit_test_collection(unit=unit_without_site)


@pytest.fixture
def test_list_instance(unit_test_collection):
    """Create a test list instance with UTC."""
    tli = utils.create_test_list_instance(unit_test_collection=unit_test_collection)
    # Make this tli autoreviewed
    tli.all_reviewed = True
    tli.reviewed_by = None
    tli.save()
    return tli


@pytest.fixture
def test_list_instance2(unit_test_collection2):
    """Create a test list instance with UTC2."""
    return utils.create_test_list_instance(unit_test_collection=unit_test_collection2)


@pytest.fixture
def test_list_instance3(unit_test_collection2, test_list_instance2):
    """Create a test list instance with history."""
    return utils.create_test_list_instance(
        unit_test_collection=unit_test_collection2,
        work_completed=test_list_instance2.work_completed - timezone.timedelta(days=2),
    )


@pytest.fixture
def test_instance(test_list_instance3):
    """Create a test instance for TLI3."""
    return utils.create_test_instance(test_list_instance=test_list_instance3)


@pytest.fixture
def toronto_timezone():
    """Create a Toronto timezone."""
    return pytz.timezone("America/Toronto")


@pytest.fixture
def work_completed_datetime(toronto_timezone):
    """Create a work completed datetime in Toronto timezone."""
    return toronto_timezone.localize(timezone.datetime(2019, 1, 1, 12))


@pytest.fixture
def frequency():
    """Create a frequency."""
    return Frequency.objects.create(name="freq", window_start=0, window_end=0)