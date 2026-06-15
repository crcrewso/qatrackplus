import os
import pytest
from unittest import mock

from django.conf import settings

from qatrack.attachments.models import Attachment
from qatrack.qa import models as qam


@pytest.fixture
def test_list_object():
    """Create a test list object."""
    return qam.TestList(name="test")


@pytest.fixture
def test_instance_object():
    """Create a test instance object."""
    return qam.TestInstance()


@pytest.fixture
def test_list_with_pk():
    """Create a test list with a primary key."""
    return qam.TestList(pk=1)


@pytest.fixture
def mock_tmp_file():
    """Create a mock file in the TMP_UPLOAD_ROOT."""
    mocka = mock.Mock()
    name = "foo.bar"
    mocka.path = os.path.join(settings.TMP_UPLOAD_ROOT, name)
    mocka.name = name
    return mocka


@pytest.fixture
def attachment_with_testlist(test_list_object):
    """Create an attachment with a test list."""
    return Attachment(testlist=test_list_object)


@pytest.fixture
def attachment_with_testinstance(test_instance_object):
    """Create an attachment with a test instance."""
    return Attachment(testinstance=test_instance_object)


@pytest.fixture
def attachment_with_tmp_file(mock_tmp_file):
    """Create an attachment with a file in TMP_UPLOAD_ROOT."""
    return Attachment(attachment=mock_tmp_file)


@pytest.fixture
def attachment_with_testlist_and_tmp_file(test_list_with_pk, mock_tmp_file):
    """Create an attachment with a test list with PK and a file in TMP_UPLOAD_ROOT."""
    return Attachment(testlist=test_list_with_pk, attachment=mock_tmp_file)