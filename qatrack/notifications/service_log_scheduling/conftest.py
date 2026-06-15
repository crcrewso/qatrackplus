import pytest
from django.contrib.admin.sites import AdminSite
from django.utils import timezone
import recurrence

from qatrack.notifications.models import (
    RecipientGroup,
    ServiceEventSchedulingNotice,
    UnitGroup,
)
from qatrack.notifications.service_log_scheduling import admin
from qatrack.service_log import models


@pytest.fixture
def service_event_scheduling_admin():
    """Create a ServiceEventSchedulingAdmin instance."""
    return admin.ServiceEventSchedulingAdmin(model=ServiceEventSchedulingNotice, admin_site=AdminSite())


@pytest.fixture
def notice_form():
    """Create a ServiceEventSchedulingNoticeAdminForm instance."""
    return admin.ServiceEventSchedulingNoticeAdminForm()


@pytest.fixture
def recipient_group():
    """Create a RecipientGroup."""
    return RecipientGroup.objects.create(name="RG")


@pytest.fixture
def unit_group():
    """Create a UnitGroup."""
    return UnitGroup.objects.create(name="UG")


@pytest.fixture
def service_area():
    """Create a ServiceArea."""
    return models.ServiceArea.objects.create(name="SA")


@pytest.fixture
def service_event_schedule():
    """Create a ServiceEventSchedule."""
    return models.ServiceEventSchedule.objects.create(
        name="Schedule",
        frequency_type=models.ServiceEventSchedule.FREQUENCY_RECURRENCE,
        recurrences=recurrence.Recurrence(
            rrules=[recurrence.Rule(recurrence.WEEKLY)],
            dtstart=timezone.datetime(2018, 1, 1, tzinfo=timezone.utc),
        ),
        due_date=timezone.now() + timezone.timedelta(days=1),
    )