"""Root pytest conftest.

Provides shared fixtures and hooks used across the entire test suite.
The screenshot-on-failure hook is only active for tests that run against
a live Selenium WebDriver instance.
"""

import os

import pytest

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), 'selenium-screenshots')


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Save a browser screenshot whenever a Selenium test fails.

    Screenshots are written to ``selenium-screenshots/`` at the repo root
    and uploaded as CI artifacts to aid debugging.
    """
    outcome = yield
    report = outcome.get_result()

    # Only act during the 'call' phase (the actual test body) and only on failure.
    if report.when != 'call' or not report.failed:
        return

    # ``item.instance`` is set for unittest.TestCase-based tests.
    instance = getattr(item, 'instance', None)
    driver = getattr(instance, 'driver', None)
    if driver is None:
        return

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # Build a filesystem-safe filename from the test node id.
    safe_name = item.nodeid.replace('/', '_').replace('::', '__').replace(' ', '_')
    screenshot_path = os.path.join(SCREENSHOT_DIR, f'{safe_name}.png')

    try:
        driver.save_screenshot(screenshot_path)
    except Exception:
        pass
