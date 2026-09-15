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
