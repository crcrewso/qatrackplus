from django.contrib.auth.models import Group, User
import rest_framework_filters as filters

from qatrack.api.auth.filters import GroupFilter, UserFilter
from qatrack.api.filters import MaxDateFilter, MinDateFilter
from qatrack.api.qa.filters import (
    FrequencyFilter,
    TestListInstanceFilter,
    UnitTestCollectionFilter,
)
from qatrack.api.units.filters import UnitFilter, VendorFilter
from qatrack.qa.models import Frequency, TestListInstance, UnitTestCollection
from qatrack.service_log import models
from qatrack.units.models import Unit, Vendor


class ServiceAreaFilter(filters.FilterSet):

    units = filters.RelatedFilter(UnitFilter, field_name='units', queryset=Unit.objects.all())

    class Meta:
        model = models.ServiceArea
        fields = {
            "name": ['exact', 'icontains', 'contains', 'in'],
        }


class UnitServiceAreaFilter(filters.FilterSet):

    unit = filters.RelatedFilter(UnitFilter, field_name='unit', queryset=Unit.objects.all())
    service_area = filters.RelatedFilter(
        ServiceAreaFilter,
        field_name='service_area',
        queryset=models.ServiceArea.objects.all(),
    )

    class Meta:
        model = models.UnitServiceArea
        fields = {
            "notes": ['exact', 'icontains', 'contains', 'in'],
        }


class ServiceTypeFilter(filters.FilterSet):

    class Meta:
        model = models.ServiceType
        fields = {
            "name": ['exact', 'icontains', 'contains', 'in'],
            "is_review_required": ['exact'],
            "is_active": ['exact'],
            "description": ['exact', 'icontains', 'contains', 'in'],
        }


class ServiceEventStatusFilter(filters.FilterSet):

    class Meta:
        model = models.ServiceEventStatus
        fields = {
            "name": ['exact', 'icontains', 'contains', 'in'],
            "is_review_required": ['exact'],
            "is_default": ['exact'],
            "rts_qa_must_be_reviewed": ['exact'],
            "description": ['exact', 'icontains', 'contains', 'in'],
            "colour": ['exact', 'icontains', 'contains', 'in'],
        }


class ServiceEventScheduleFilter(filters.FilterSet):

    unit_service_area = filters.RelatedFilter(
        UnitServiceAreaFilter,
        field_name='unit_service_area',
        queryset=models.UnitServiceArea.objects.select_related("unit", "service_area"),
    )

    frequency = filters.RelatedFilter(FrequencyFilter, field_name="frequency", queryset=Frequency.objects.all())
    assigned_to = filters.RelatedFilter(GroupFilter, field_name="assigned_to", queryset=Group.objects.all())

    due_date_min = MinDateFilter(field_name="due_date")
    due_date_max = MaxDateFilter(field_name="due_date")

    class Meta:
        model = models.ServiceEventSchedule
        fields = {
            "auto_schedule": ['exact'],
            "active": ['exact'],
        }


class ServiceEventFilter(filters.FilterSet):

    unit_service_area = filters.RelatedFilter(
        UnitServiceAreaFilter,
        field_name='unit_service_area',
        queryset=models.UnitServiceArea.objects.select_related("unit", "service_area"),
    )
    service_type = filters.RelatedFilter(
        ServiceTypeFilter,
        field_name='service_type',
        queryset=models.ServiceType.objects.all(),
    )
    service_event_related = filters.RelatedFilter(
        'ServiceEventFilter', field_name='service_event_related', queryset=models.ServiceEvent.objects.all()
    )
    service_status = filters.RelatedFilter(
        ServiceEventStatusFilter,
        field_name='service_status',
        queryset=models.ServiceEventStatus.objects.all(),
    )
    service_event_schedule = filters.RelatedFilter(
        ServiceEventScheduleFilter,
        field_name='service_event_schedule',
        queryset=models.ServiceEventSchedule.objects.all(),
    )
    user_status_changed_by = filters.RelatedFilter(
        UserFilter,
        field_name='user_status_changed_by',
        queryset=User.objects.all(),
    )
    user_created_by = filters.RelatedFilter(UserFilter, field_name='user_created_by', queryset=User.objects.all())
    user_modified_by = filters.RelatedFilter(UserFilter, field_name='user_modified_by', queryset=User.objects.all())
    test_list_instance_initiated_by = filters.RelatedFilter(
        TestListInstanceFilter,
        field_name='test_list_instance_initiated_by',
        queryset=TestListInstance.objects.all(),
    )

    datetime_status_changed_min = MinDateFilter(field_name="datetime_status_changed")
    datetime_status_changed_max = MaxDateFilter(field_name="datetime_status_changed")
    due_date_min = MinDateFilter(field_name="due_date")
    due_date_max = MaxDateFilter(field_name="due_date")
    datetime_service_min = MinDateFilter(field_name="datetime_service")
    datetime_service_max = MaxDateFilter(field_name="datetime_service")
    datetime_created_min = MinDateFilter(field_name="datetime_created")
    datetime_created_max = MaxDateFilter(field_name="datetime_created")
    datetime_modified_min = MinDateFilter(field_name="datetime_modified")
    datetime_modified_max = MaxDateFilter(field_name="datetime_modified")

    class Meta:
        model = models.ServiceEvent
        fields = {
            'due_date': ['exact'],
            'datetime_status_changed': ['exact'],
            'datetime_created': ['exact'],
            'datetime_service': ['exact'],
            'datetime_modified': ['exact'],
            'safety_precautions': ['exact', 'icontains', 'contains', 'in'],
            'problem_description': ['exact', 'icontains', 'contains', 'in'],
            'duration_service_time': ['lte', 'gte'],
            'duration_lost_time': ['lte', 'gte'],
            'is_review_required': ['exact'],
            'include_for_scheduling': ['exact'],
        }


class ServiceEventTemplateFilter(filters.FilterSet):

    service_type = filters.RelatedFilter(
        ServiceTypeFilter,
        field_name='service_type',
        queryset=models.ServiceType.objects.all(),
    )
    service_area = filters.RelatedFilter(
        ServiceAreaFilter,
        field_name='service_area',
        queryset=models.ServiceArea.objects.all(),
    )
    created_by = filters.RelatedFilter(UserFilter, field_name='created_by', queryset=User.objects.all())
    modified_by = filters.RelatedFilter(UserFilter, field_name='modified_by', queryset=User.objects.all())

    class Meta:
        model = models.ServiceEventTemplate
        fields = {
            'created': ['exact'],
            'modified': ['exact'],
            'problem_description': ['exact', 'icontains', 'contains', 'in'],
            'work_description': ['exact', 'icontains', 'contains', 'in'],
            'is_review_required': ['exact'],
        }


class ThirdPartyFilter(filters.FilterSet):

    vendor = filters.RelatedFilter(VendorFilter, field_name='vendor', queryset=Vendor.objects.all())

    class Meta:
        model = models.ThirdParty
        fields = {
            'first_name': ['exact', 'icontains', 'contains', 'in'],
            'last_name': ['exact', 'icontains', 'contains', 'in'],
        }


class HoursFilter(filters.FilterSet):

    service_event = filters.RelatedFilter(
        ServiceEventFilter, field_name='service_event', queryset=models.ServiceEvent.objects.all()
    )
    third_party = filters.RelatedFilter(
        ThirdPartyFilter,
        field_name='third_party',
        queryset=models.ThirdParty.objects.all(),
    )

    class Meta:
        model = models.Hours
        fields = {
            'time': ['lte', 'gte'],
        }


class ReturnToServiceQAFilter(filters.FilterSet):

    unit_test_collection = filters.RelatedFilter(
        UnitTestCollectionFilter, field_name='unit_test_collection', queryset=UnitTestCollection.objects.all()
    )
    test_list_instance = filters.RelatedFilter(
        TestListInstanceFilter, field_name='test_list_instance', queryset=TestListInstance.objects.all()
    )
    user_assigned_by = filters.RelatedFilter(UserFilter, field_name='user_assigned_by', queryset=User.objects.all())
    service_event = filters.RelatedFilter(
        ServiceEventFilter, field_name='service_event', queryset=models.ServiceEvent.objects.all()
    )

    datetime_assigned_min = MinDateFilter(field_name="datetime_assigned")
    datetime_assigned_max = MaxDateFilter(field_name="datetime_assigned")

    class Meta:
        model = models.ReturnToServiceQA
        fields = {
            'datetime_assigned': ['exact'],
        }


class GroupLinkerFilter(filters.FilterSet):

    group = filters.RelatedFilter(GroupFilter, field_name='group', queryset=Group.objects.all())

    class Meta:
        model = models.GroupLinker
        fields = {
            "name": ['exact', 'icontains', 'contains', 'in'],
            "description": ['exact', 'icontains', 'contains', 'in'],
            "help_text": ['icontains'],
        }


class GroupLinkerInstanceFilter(filters.FilterSet):

    group_linker = filters.RelatedFilter(
        GroupLinkerFilter, field_name='group_linker', queryset=models.GroupLinker.objects.all()
    )
    user = filters.RelatedFilter(UserFilter, field_name='user', queryset=User.objects.all())
    service_event = filters.RelatedFilter(
        ServiceEventFilter, field_name='service_event', queryset=models.ServiceEvent.objects.all()
    )

    datetime_linked_min = MinDateFilter(field_name="datetime_linked")
    datetime_linked_max = MaxDateFilter(field_name="datetime_linked")

    class Meta:
        model = models.GroupLinkerInstance
        fields = {
            'datetime_linked': ['exact'],
        }
