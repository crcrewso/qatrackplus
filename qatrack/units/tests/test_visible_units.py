"""Which units a user may log QC or faults against.

#883 (4.0.2) exempted holders of `qa.can_review_non_visible_tli` - every
superuser - from `visible_to` narrowing on the QC views, but missed
`units_visible_to_user`, so the fault form's Unit select was empty for a
superuser in no groups and the form could not be saved (aviary B76).
"""

from django.test import TestCase

from qatrack.qa.tests import utils
from qatrack.units.forms import unit_site_unit_type_choices, units_visible_to_user


class TestUnitsVisibleToUser(TestCase):

    def setUp(self):
        self.group = utils.create_group()
        self.unit = utils.create_unit(name="u1")
        utc = utils.create_unit_test_collection(unit=self.unit)
        utc.visible_to.set([self.group])

    def test_a_superuser_in_no_groups_sees_the_unit(self):
        user = utils.create_user(is_superuser=True)
        user.groups.clear()
        assert list(units_visible_to_user(user)) == [self.unit]

    def test_a_member_of_the_group_sees_the_unit(self):
        user = utils.create_user(is_superuser=False)
        user.groups.set([self.group])
        assert list(units_visible_to_user(user)) == [self.unit]

    def test_a_plain_user_in_no_groups_sees_nothing(self):
        user = utils.create_user(is_superuser=False)
        user.groups.clear()
        user.user_permissions.clear()  # the factory grants every permission, including the exemption
        assert list(units_visible_to_user(user)) == []

    def test_the_fault_form_choices_follow(self):
        user = utils.create_user(is_superuser=True)
        user.groups.clear()
        choices = unit_site_unit_type_choices(include_empty=True, serviceable_only=True, visible_for_user=user)
        flat = str(choices)
        assert "u1" in flat
