import pytest
from django.contrib.admin.sites import AdminSite
from django.utils import timezone

from qatrack.accounts.tests.utils import create_user
from qatrack.notifications.models import (
    QCCompletedNotice,
    RecipientGroup,
    TestListGroup,
    UnitGroup,
)
from qatrack.notifications.qccompleted import admin


@pytest.fixture
def user_with_credentials():
    """Create a superuser with credentials."""
    return create_user(is_superuser=True, uname='user', pwd='pwd')


@pytest.fixture
def qc_completed_admin():
    """Create a QCCompletedAdmin instance."""
    return admin.QCCompletedAdmin(model=QCCompletedNotice, admin_site=AdminSite())


@pytest.fixture
def url_add():
    """Get the URL for adding a QCCompletedNotice."""
    return '/admin/notifications/qccompletednotice/add/'


@pytest.fixture
def url_list():
    """Get the URL for QCCompletedNotice list view."""
    return '/admin/notifications/qccompletednotice/'


@pytest.fixture
def recipient_group():
    """Create a RecipientGroup."""
    return RecipientGroup.objects.create(name="RG")


@pytest.fixture
def unit_group():
    """Create a UnitGroup."""
    return UnitGroup.objects.create(name="UG")


@pytest.fixture
def test_list_group():
    """Create a TestListGroup."""
    return TestListGroup.objects.create(name="TLG")