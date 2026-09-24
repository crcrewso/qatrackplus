"""click_by_css_selector's two failure paths, without a browser.

An element that is covered and an element that has been replaced both arrive
as a WebDriverException and need opposite handling: the first wants a JS
click that ignores overlays, the second wants to be found again. Getting
them the wrong way round is silent - JS-clicking a dead reference raises the
same staleness error one line lower, so the failure reads as though the
fallback broke rather than as a stale element.

The real trigger is a date picker still closing while `.open .today` is
matched against it, which is timing-dependent and does not reproduce on
demand. This drives each path directly instead.
"""
from django.test import SimpleTestCase
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

from qatrack.qatrack_core.tests.live import SeleniumTests


class _Element:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.clicked = False

    def click(self):
        if self.behaviour == 'stale':
            raise StaleElementReferenceException("element is not attached")
        if self.behaviour == 'intercepted':
            raise ElementClickInterceptedException("element click intercepted")
        self.clicked = True


class _Driver:
    """Hands out an element per find_element call, per the script given."""

    def __init__(self, *behaviours):
        self.behaviours = list(behaviours)
        self.found = []
        self.js_clicks = []

    def find_element(self, by, value):
        behaviour = self.behaviours.pop(0) if self.behaviours else 'ok'
        element = _Element(behaviour)
        self.found.append(element)
        return element

    def execute_script(self, script, *args):
        self.js_clicks.append(args)


class _Harness:
    """Enough of SeleniumTests for the helper under test."""

    def __init__(self, driver):
        self.driver = driver
        self.scrolls = 0

    def scroll_into_view_css(self, css_sel):
        self.scrolls += 1


def _click(driver):
    harness = _Harness(driver)
    SeleniumTests.click_by_css_selector(harness, ".open .today")
    return harness


class TestClickReFindsAStaleElement(SimpleTestCase):

    def test_a_stale_element_is_found_again_and_clicked(self):
        driver = _Driver('stale', 'ok')
        _click(driver)

        assert len(driver.found) == 2, "did not re-find after staleness"
        assert driver.found[1].clicked
        assert driver.js_clicks == [], "JS-clicked a dead reference"

    def test_it_rescrolls_before_each_attempt(self):
        """The element moved; its position is not assumed to have survived."""
        harness = _click(_Driver('stale', 'ok'))
        assert harness.scrolls == 2

    def test_it_gives_up_rather_than_spinning(self):
        driver = _Driver('stale', 'stale', 'stale')
        with self.assertRaises(StaleElementReferenceException):
            _click(driver)
        assert len(driver.found) == 3


class TestClickFallsBackForACoveredElement(SimpleTestCase):

    def test_an_intercepted_click_uses_javascript(self):
        driver = _Driver('intercepted')
        _click(driver)

        assert len(driver.js_clicks) == 1, "did not fall back to a JS click"
        assert driver.js_clicks[0] == (driver.found[0],)
        assert len(driver.found) == 1, "retried instead of falling back"

    def test_interception_is_not_retried(self):
        """Re-finding a covered element just finds the same covered element."""
        driver = _Driver('intercepted', 'ok')
        _click(driver)
        assert len(driver.found) == 1


class TestTheOrdinaryCase(SimpleTestCase):

    def test_a_clickable_element_is_clicked_directly(self):
        driver = _Driver('ok')
        _click(driver)

        assert driver.found[0].clicked
        assert driver.js_clicks == []
        assert len(driver.found) == 1
