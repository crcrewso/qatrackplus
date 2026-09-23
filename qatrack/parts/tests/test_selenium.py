import pytest

from qatrack.qa.tests.test_selenium import BaseQATests


@pytest.mark.skip(reason="stub - not yet implemented")
class TestPartsReporting(BaseQATests):
    """Selenium coverage for the parts cost report
    (parts/parts_units_cost.html, driven by parts_reporting.js).

    The parts app has no Selenium coverage of any kind today. This page
    loads one of the three JS modules corrected in #824, where a missing
    RequireJS dependency surfaced only as a browser console error - the
    class of bug a server-side test cannot see.
    """

    def test_parts_units_cost_loads(self):
        """Open the parts-by-unit cost report and confirm the table and
        its date-range filter render."""
        raise NotImplementedError

    def test_parts_units_cost_has_no_console_errors(self):
        """Assert no SEVERE browser-console entries on load."""
        raise NotImplementedError
