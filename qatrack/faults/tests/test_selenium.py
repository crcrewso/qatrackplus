import time

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from qatrack.accounts.tests.utils import create_group
from qatrack.faults import models
from qatrack.faults.tests import utils as fault_utils
from qatrack.qa.tests import utils as qa_utils
from qatrack.qa.tests.test_selenium import BaseQATests


@pytest.mark.selenium
class TestFaultForm(BaseQATests):
    """Coverage for the Fault create/edit form (/faults/create/,
    /faults/edit/<pk>/). Like the Service Event form, this uses the same
    flatpickr/DateTimeInput widget family (`occurred`) that had the
    autosave date-format bug fixed elsewhere on this branch, and had no
    Selenium coverage at all.
    """

    def setUp(self):
        super().setUp()

        self.group = create_group()
        for p in Permission.objects.all():
            self.group.permissions.add(p)
        self.user.groups.add(self.group)

        self.unit = qa_utils.create_unit()
        self.fault_type = fault_utils.create_fault_type(code="ABC")

        # The unit ChoiceField on the fault form is restricted to units
        # visible to the current user's groups via an active
        # UnitTestCollection (see units.forms.units_visible_to_user) -
        # without this, the unit dropdown is empty regardless of the
        # user's actual permissions.
        utc = qa_utils.create_unit_test_collection(unit=self.unit)
        utc.visible_to.add(self.group)

    def select_unit(self, unit):
        # id_fault-unit is a select2 whose choices are grouped by
        # site/unit-type (optgroups) - SeleniumTests.select_by_index's
        # plain-select fallback counts flat option indexes, which doesn't
        # line up cleanly with grouped choices. Setting the value
        # directly and triggering select2's own 'change' handler is more
        # reliable here than guessing an index.
        self.driver.execute_script("$('#id_fault-unit').val(arguments[0]).trigger('change');", str(unit.pk))

    def select_fault_type(self, code):
        # id_fault-fault_types_field is an AJAX-autocomplete select2 tag
        # widget (server-side search, 2+ characters, debounced) - rather
        # than fight that timing in a test, add + select the option on
        # the underlying <select multiple> directly and fire the change
        # event the widget's own JS listens for, exactly like the plain-
        # select fallback SeleniumTests.select_by_* already use elsewhere
        # for a select2 that doesn't behave like a normal dropdown.
        self.driver.execute_script(
            """
            var sel = document.getElementById('id_fault-fault_types_field');
            var opt = document.createElement('option');
            opt.value = arguments[0];
            opt.text = arguments[0];
            opt.selected = true;
            sel.appendChild(opt);
            sel.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            code,
        )

    def wait_for_fault_list(self):
        self.wait.until(lambda d: d.current_url.rstrip('/').endswith('/faults'))

    def test_create_fault(self):
        """Create a fault directly via /faults/create/"""

        self.login()
        self.open(reverse('fault_create'))
        time.sleep(0.3)

        self.select_unit(self.unit)
        time.sleep(0.2)
        self.select_fault_type(self.fault_type.code)
        # Unlike the perform-QC/service-event flatpickr instances, this
        # one has no "today" quick-link - it auto-fills "now" via its own
        # onOpen handler as soon as the (empty) field is focused.
        self.driver.execute_script("$('#id_fault-occurred').focus()")
        time.sleep(0.3)
        self.click_by_css_selector("body")
        time.sleep(0.2)
        self.send_keys("id_fault-comment", "Test fault comment")

        fault_count = models.Fault.objects.count()
        self.click_by_css_selector("button[type=submit]")
        # A successful save redirects to the fault list.
        self.wait_for_fault_list()
        time.sleep(0.2)

        assert models.Fault.objects.count() == fault_count + 1
        fault = models.Fault.objects.latest("pk")
        assert fault.unit_id == self.unit.pk
        assert self.fault_type in fault.fault_types.all()

    def test_edit_fault(self):
        """Edit an existing fault via /faults/edit/<pk>/"""

        fault = fault_utils.create_fault(unit=self.unit, fault_type=self.fault_type, user=self.user)

        self.login()
        self.open(reverse('fault_edit', kwargs={'pk': fault.pk}))
        time.sleep(0.3)

        # The existing fault type should already be selected - confirm
        # the round trip before changing anything, same rationale as the
        # equivalent check in the Service Event form test.
        selected = self.driver.execute_script(
            "return Array.from(document.getElementById('id_fault-fault_types_field').selectedOptions)"
            ".map(function(o){ return o.value; });"
        )
        assert self.fault_type.code in selected

        new_fault_type = fault_utils.create_fault_type(code="XYZ")
        self.select_fault_type(new_fault_type.code)

        self.click_by_css_selector("button[type=submit]")
        self.wait_for_fault_list()
        time.sleep(0.2)

        fault.refresh_from_db()
        assert new_fault_type in fault.fault_types.all()
