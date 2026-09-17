import os

import pytest

# The original idiom for excluding GUI tests, predating --run-selenium.
# Kept fully working (see pytest_collection_modifyitems below) but
# deprecated as of 4.0, for removal in 4.2: it needs quoting on every
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


@pytest.fixture(autouse=True, scope='session')
def _xdist_worker_media_root(tmp_path_factory):
    """Give each xdist worker its own MEDIA_ROOT.

    pytest-django already hands each worker a separate test database, and
    LiveServerTestCase already binds a free port per instance, so the
    database and the web server are isolated for free. The filesystem is
    not: MEDIA_ROOT, UPLOAD_ROOT and TMP_UPLOAD_ROOT all point inside
    qatrack/media, which every worker would otherwise write to at once -
    upload tests clobbering each other's files, and tmp uploads being
    cleaned up out from under a different worker.

    Redirecting them per worker is what makes `-n` safe. Outside xdist
    (PYTEST_XDIST_WORKER unset) this is a no-op, so a serial run still
    uses the real media directory exactly as before.
    """
    worker = os.environ.get('PYTEST_XDIST_WORKER')
    if not worker:
        yield
        return

    from django.test import override_settings

    root = tmp_path_factory.mktemp('media-%s' % worker)
    uploads = root / 'uploads'
    tmp_uploads = uploads / 'tmp'
    tmp_uploads.mkdir(parents=True, exist_ok=True)

    with override_settings(
        MEDIA_ROOT=str(root),
        UPLOAD_ROOT=str(uploads),
        TMP_UPLOAD_ROOT=str(tmp_uploads),
    ):
        yield
