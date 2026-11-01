"""Which units a user may log QC or faults against.

#883 (4.0.2) exempted holders of `qa.can_review_non_visible_tli` - every
superuser - from `visible_to` narrowing on the QC views, but missed
`units_visible_to_user`, so the fault form's Unit select was empty for a
superuser in no groups and the form could not be saved (aviary B76).
"""

from django.contrib.auth.models import User
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
        user = utils.create_user(is_superuser=True, uname="super")
        user.groups.clear()
        assert list(units_visible_to_user(user)) == [self.unit]

    def test_a_member_of_the_group_sees_the_unit(self):
        user = utils.create_user(is_superuser=False, uname="member")
        user.groups.set([self.group])
        assert list(units_visible_to_user(user)) == [self.unit]

    def test_a_plain_user_in_no_groups_sees_nothing(self):
        # The factory returns an existing user of the same name, and the other
        # factories create a superuser called "user", so the name matters.
        user = utils.create_user(is_superuser=False, uname="plain")
        user.groups.clear()
        user.user_permissions.clear()  # the factory grants every permission, including the exemption
        user = User.objects.get(pk=user.pk)  # drop the cached permission set
        assert list(units_visible_to_user(user)) == []

    def test_the_fault_form_choices_follow(self):
        user = utils.create_user(is_superuser=True, uname="super")
        user.groups.clear()
        choices = unit_site_unit_type_choices(include_empty=True, serviceable_only=True, visible_for_user=user)
        flat = str(choices)
        assert "u1" in flat
