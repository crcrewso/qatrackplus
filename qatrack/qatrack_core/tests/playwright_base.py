"""
playwright_base.py
~~~~~~~~~~~~~~~~~~

Base infrastructure for Playwright browser tests in QATrack+.

This module replaces the legacy Selenium-based ``live.py`` / ``selenium_test.py``
modules.  It provides:

* A ``conftest``-compatible set of pytest fixtures that configure and launch
  a Playwright browser according to the ``PLAYWRIGHT_BROWSER``,
  ``PLAYWRIGHT_HEADLESS``, and ``PLAYWRIGHT_SLOW_MO`` Django settings.
* A ``PlaywrightTests`` mixin with helper methods that mirror the helper
  interface that was previously available in ``SeleniumTests``, making it
  straightforward to migrate existing test classes.

Usage
-----

In a pytest-based test class::

    import pytest
    from django.test import TransactionTestCase
    from qatrack.qatrack_core.tests.playwright_base import PlaywrightTests

    @pytest.mark.browser
    class MyBrowserTests(PlaywrightTests, TransactionTestCase):

        def test_something(self):
            self.open("/some/url/")
            self.click("some-button-id")
            self.page.locator(".result").wait_for()

The ``self.page`` and ``self.live_server_url`` attributes are set up
automatically by the ``PlaywrightTests.setUpClass`` / ``setUp`` machinery,
which is driven by the ``playwright_page`` pytest fixture declared at the
bottom of this module.
"""

import pytest
from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope='session')
def browser_type_launch_args(browser_type_launch_args):
    """Override pytest-playwright default launch args with project settings."""
    headless = getattr(settings, 'PLAYWRIGHT_HEADLESS', True)
    slow_mo = getattr(settings, 'PLAYWRIGHT_SLOW_MO', 0)
    return {**browser_type_launch_args, 'headless': headless, 'slow_mo': slow_mo}


@pytest.fixture(scope='session')
def browser_context_args(browser_context_args):
    """Set a sensible default viewport for all browser tests."""
    return {**browser_context_args, 'viewport': {'width': 1920, 'height': 1080}}


@pytest.fixture(scope='session')
def playwright_browser_name():
    """Return the browser name from Django settings (default: chromium)."""
    return getattr(settings, 'PLAYWRIGHT_BROWSER', 'chromium')


# ---------------------------------------------------------------------------
# JS coverage fixture (Chromium only)
# ---------------------------------------------------------------------------


@pytest.fixture
def js_coverage(page: Page):
    """
    Collect V8 JavaScript coverage for the current test (Chromium only).

    Usage in a test::

        def test_something(self, page, js_coverage):
            page.goto("/")
            # js_coverage fixture automatically starts/stops collection and
            # writes an LCOV file to ./coverage/js/<test_name>.json

    The raw coverage data is written to ``coverage/js/<node_id>.json`` and
    can be converted to LCOV/HTML with `c8` or `istanbul`::

        npx c8 report --reporter=html
    """
    import json
    import os

    is_chromium = 'chromium' in (page.context.browser.browser_type.name if page.context.browser else '')
    if is_chromium:
        page.coverage.start_js_coverage()

    yield

    if is_chromium:
        coverage_data = page.coverage.stop_js_coverage()
        out_dir = os.path.join('coverage', 'js')
        os.makedirs(out_dir, exist_ok=True)
        # Use the pytest node id to build a safe filename.
        test_name = os.environ.get('PYTEST_CURRENT_TEST', 'unknown').replace('/', '_').replace('::', '__')
        out_path = os.path.join(out_dir, f'{test_name}.json')
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(coverage_data, fh)


# ---------------------------------------------------------------------------
# PlaywrightTests mixin
# ---------------------------------------------------------------------------


class PlaywrightTests(StaticLiveServerTestCase):
    """
    Base class for Playwright browser tests.

    Subclass this together with ``TransactionTestCase`` (or plain
    ``TestCase``) and mark the class with ``@pytest.mark.browser``::

        @pytest.mark.browser
        class MyTests(PlaywrightTests, TransactionTestCase):
            ...

    Attributes
    ----------
    page : playwright.sync_api.Page
        The Playwright ``Page`` object for the current test.  Set in
        ``setUp`` via the ``_playwright_page`` class attribute which is
        populated by the ``playwright_page`` pytest fixture.
    live_server_url : str
        The URL of the Django live-server thread.
    """

    static_handler = StaticFilesHandler

    # Set by the ``playwright_page`` fixture before each test method.
    _playwright_page: Page = None

    def setUp(self):
        super().setUp()
        if self._playwright_page is None:  # pragma: no cover
            raise RuntimeError(
                'PlaywrightTests requires the pytest-playwright plugin and the '
                '"playwright_page" fixture to be active.  Make sure pytest-playwright '
                'is installed and the test is collected by pytest.'
            )
        self.page = self._playwright_page
        # Give every page a reference to the live server URL so that helper
        # methods can build absolute URLs.
        self._base_url = self.live_server_url

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def open(self, url: str) -> None:
        """Navigate to *url* relative to the live server root."""
        self.page.goto(self._base_url + url)

    # ------------------------------------------------------------------
    # Element interaction helpers
    # ------------------------------------------------------------------

    def click(self, el_id: str) -> None:
        """Click the element with *el_id* as its HTML ``id`` attribute."""
        self.page.locator(f'#{el_id}').click()

    def click_by_css_selector(self, css_sel: str) -> None:
        """Click the first element matching *css_sel*."""
        self.page.locator(css_sel).click()

    def click_by_link_text(self, link_text: str) -> None:
        """Click the first ``<a>`` whose visible text equals *link_text*."""
        self.page.get_by_role('link', name=link_text, exact=True).click()

    def send_keys(self, el_id: str, text: str) -> None:
        """Fill *text* into the element with id *el_id* (replaces existing value)."""
        self.page.locator(f'#{el_id}').fill(text)

    def scroll_into_view(self, el_id: str) -> None:
        """Scroll the element with id *el_id* into the visible viewport."""
        self.page.locator(f'#{el_id}').scroll_into_view_if_needed()

    def scroll_into_view_css(self, css_sel: str) -> None:
        """Scroll the first element matching *css_sel* into the visible viewport."""
        self.page.locator(css_sel).scroll_into_view_if_needed()

    # ------------------------------------------------------------------
    # Select / Select2 helpers
    # ------------------------------------------------------------------

    def select_by_index(self, el_id: str, index: int) -> None:
        """
        Select the option at *index* in a ``<select>`` or Select2 widget.

        Negative indices are supported (e.g. ``-1`` selects the last option).
        """
        locator = self.page.locator(f'#{el_id}')
        # Detect Select2 by checking whether the companion container exists.
        sel2_container = self.page.locator(f'#select2-{el_id}-container')
        if sel2_container.count() > 0:
            sel2_container.click()
            options = self.page.locator('.select2-results__option')
            options.nth(index).click()
        else:
            # Native <select>: collect all option values and pick by index.
            option_values = locator.evaluate('el => Array.from(el.options).map(o => o.value)')
            locator.select_option(value=option_values[index])

    def select_by_text(self, el_id: str, text: str) -> None:
        """
        Select the option whose visible label equals *text* in a ``<select>``
        or Select2 widget.
        """
        locator = self.page.locator(f'#{el_id}')
        sel2_container = self.page.locator(f'#select2-{el_id}-container')
        if sel2_container.count() > 0:
            sel2_container.click()
            self.page.get_by_role('option', name=text, exact=True).click()
        else:
            locator.select_option(label=text)

    def select_by_value(self, el_id: str, value: str) -> None:
        """
        Select the option with *value* in a ``<select>`` or Select2 widget.
        """
        locator = self.page.locator(f'#{el_id}')
        sel2_container = self.page.locator(f'#select2-{el_id}-container')
        if sel2_container.count() > 0:
            sel2_container.click()
            # Select2 option IDs end with the value.
            self.page.locator(f'.select2-results__option[id$="{value}"]').click()
        else:
            locator.select_option(value=value)

    # ------------------------------------------------------------------
    # Wait / assertion helpers
    # ------------------------------------------------------------------

    def wait_for_success(self) -> None:
        """Wait until a Django admin success message is visible on the page."""
        self.page.locator('ul.messagelist li.success').wait_for()

    def wait_for_page_load(self) -> None:
        """Wait for the page to reach the ``networkidle`` ready state."""
        self.page.wait_for_load_state('networkidle')

    def wait_for_element(self, selector: str) -> None:
        """Wait until the element matching *selector* is visible."""
        expect(self.page.locator(selector)).to_be_visible()

    def wait_for_element_by_id(self, el_id: str) -> None:
        """Wait until the element with *el_id* is visible."""
        expect(self.page.locator(f'#{el_id}')).to_be_visible()


# ---------------------------------------------------------------------------
# pytest fixture that wires the Playwright page into PlaywrightTests instances
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def playwright_page(request, page: Page):
    """
    Inject the Playwright ``Page`` into ``PlaywrightTests`` test instances.

    This fixture is ``autouse=True`` so it runs for every test, but it only
    modifies test instances that are subclasses of ``PlaywrightTests``.
    """
    instance = request.instance
    if isinstance(instance, PlaywrightTests):
        instance.__class__._playwright_page = page
    yield
