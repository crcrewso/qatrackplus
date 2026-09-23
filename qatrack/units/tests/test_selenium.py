import pytest

from qatrack.qa.tests.test_selenium import BaseQATests


@pytest.mark.skip(reason="stub - not yet implemented")
class TestUnitAvailableTime(BaseQATests):
    """Selenium coverage for the unit "available time" editor
    (unit_available_time). Zero Selenium coverage exists for this app at
    all today - qatrack/units/tests/test_units.py's TestUnitAvailableTime/
    TestUnitAvailableTimeEdit test the model/view logic directly, but
    nothing drives the actual editor page through a browser.
    """

    def test_edit_unit_available_time(self):
        """Open the unit available time editor for a unit and add/edit a
        schedule entry through the UI."""
        raise NotImplementedError


@pytest.mark.skip(reason="stub - not yet implemented")
class TestUnitsList(BaseQATests):
    """Selenium coverage for the units list (units/units_list.html), which
    loads parts_reporting.js - one of the three modules #824 had to add a
    missing RequireJS dependency to, none of which any test drives.
    """

    def test_units_list_loads(self):
        """Open the units list and confirm the table renders and its
        per-unit action menu is usable."""
        raise NotImplementedError

    def test_units_list_has_no_console_errors(self):
        """Assert no SEVERE browser-console entries on load - the same
        check as the QA overview stub, for the other page that shares
        the affected JS bundle."""
        raise NotImplementedError
