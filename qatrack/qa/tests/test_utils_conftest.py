import io
import json
import pytest
from unittest import mock

from django.conf import settings
from django.test.utils import override_settings

from qatrack.qa import models, testpack
from qatrack.qa import utils as qautils


@pytest.fixture
def io_stringio():
    """Create a StringIO object."""
    return io.StringIO()


@pytest.fixture
def test_import_export_setup(user, test_list_named_tl1, test_list_named_tl2, test_list_named_tl3,
                          test_cycle, test_named_t1, test_named_t2, test_named_t3, test_named_t4):
    """Setup for TestImportExport class."""
    utils.create_test_list_membership(test_list_named_tl1, test_named_t1)
    utils.create_test_list_membership(test_list_named_tl2, test_named_t2)
    utils.create_test_list_membership(test_list_named_tl3, test_named_t3)
    utils.create_test_list_membership(test_list_named_tl3, test_named_t1)

    tlqs = models.TestList.objects.filter(pk=test_list_named_tl3.pk)
    tlcqs = models.TestListCycle.objects.filter(pk=test_cycle.pk)
    extra = models.Test.objects.filter(pk=test_named_t4.pk)
    
    return {
        'user': user,
        'tl1': test_list_named_tl1,
        'tl2': test_list_named_tl2,
        'tl3': test_list_named_tl3,
        'tlc': test_cycle,
        't1': test_named_t1,
        't2': test_named_t2,
        't3': test_named_t3,
        't4': test_named_t4,
        'tlqs': tlqs,
        'tlcqs': tlcqs,
        'extra': extra
    }


@pytest.fixture
def test_named_t1():
    """Create a test named t1."""
    return utils.create_test("t1")


@pytest.fixture
def test_named_t2():
    """Create a test named t2."""
    return utils.create_test("t2")


@pytest.fixture
def test_named_t3():
    """Create a test named t3."""
    return utils.create_test("t3")


@pytest.fixture
def test_named_t4():
    """Create a test named t4."""
    return utils.create_test("t4")


@pytest.fixture
def test_list_named_tl1():
    """Create a test list named tl1."""
    return utils.create_test_list("tl1 é")


@pytest.fixture
def test_list_named_tl2():
    """Create a test list named tl2."""
    return utils.create_test_list("tl2")


@pytest.fixture
def test_list_named_tl3():
    """Create a test list named tl3."""
    return utils.create_test_list("tl3")


@pytest.fixture
def test_list_named_tl5():
    """Create a test list named tl5."""
    return utils.create_test_list("tl5")
    

@pytest.fixture
def test_named_t5():
    """Create a test named t5."""
    return utils.create_test("t5")