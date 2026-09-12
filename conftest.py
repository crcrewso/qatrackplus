import pytest

# The original idiom for excluding GUI tests, predating --run-selenium.
# Kept fully working (see pytest_collection_modifyitems below) but
# deprecated as of 4.1, for removal in 4.2: it needs quoting on every
# shell because of the space, when plain `pytest` now does the same
# thing with nothing to type at all.
_DEPRECATED_EXCLUDE_MARKEXPR = 'not selenium'


def pytest_addoption(parser):
    parser.addoption(
        '--run-selenium',
        action='store_true',
        default=False,
        help=(
            "Also run the GUI (Selenium/browser) tests, which need a real "
            "Chromium or Firefox installed on the host. Skipped by default."
        ),
    )


def pytest_configure(config):
    markexpr = (config.getoption('markexpr') or '').strip()
    if markexpr == _DEPRECATED_EXCLUDE_MARKEXPR:
        config.issue_config_time_warning(
            pytest.PytestDeprecationWarning(
                'pytest -m "not selenium" is deprecated - GUI/Selenium tests '
                'are now skipped by default, so plain `pytest` does the same '
                'thing without the quoting. This form still works today but '
                'will be removed in QATrack+ 4.2; switch to plain `pytest` '
                '(or `pytest --run-selenium` to also run the GUI tests).'
            ),
            stacklevel=2,
        )


def pytest_collection_modifyitems(config, items):
    # Only apply the auto-skip on a plain invocation. If the caller already
    # passed their own -m/--markexpr (e.g. `pytest -m selenium` to run just
    # the GUI tests, or the deprecated `pytest -m "not selenium"`), trust
    # that explicit selection instead of second-guessing it here.
    if config.getoption('--run-selenium') or config.getoption('markexpr'):
        return

    skip_selenium = pytest.mark.skip(
        reason="GUI test - needs a real browser; pass --run-selenium (or select explicitly with -m) to run it"
    )
    for item in items:
        if 'selenium' in item.keywords:
            item.add_marker(skip_selenium)
