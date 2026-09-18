# Test-specific settings for QATrack+ - SQLite in-memory variant
# Copy this file to qatrack/local_test_settings.py and customize as needed
#
# Faster than the file-based sqlite variant since nothing touches disk, at
# the cost of not being able to inspect the database file after a test run.
#
# This file's job is to say which database the test suite should use.
#
# Everything else that makes the suite deterministic is already set by
# qatrack/test_settings.py, which is imported immediately before this file:
# DEBUG, NOTIFICATIONS_ON, DEFAULT_NUMBER_FORMAT, AD_CLEAN_USERNAME,
# HTTP_OR_HTTPS, REVIEW_BULK, TIME_ZONE, AUTHENTICATION_BACKENDS and the
# password hasher. Repeating any of them here just restates a value you
# already have - add a setting below only when you want to *differ* from it.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
DATABASES['readonly'] = DATABASES['default']

# Optional: pin the browser for every Selenium run, instead of choosing it
# per run on the command line. See "Setting Up Selenium Browser Testing" in
# docs/developer/guide.rst for what these do and for the one-off form.
# SELENIUM_BROWSER = 'chromium'    # 'firefox' is the default
# SELENIUM_HEADLESS = False        # watch the run in a real browser window
