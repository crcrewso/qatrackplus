# Test-specific settings for QATrack+ - MySQL variant
# Copy this file to qatrack/local_test_settings.py and customize as needed
#
# Requires the `mysql` extra: uv sync --extra mysql
#
# This file's job is to say which database the test suite should use.
#
# Everything else that makes the suite deterministic is already set by
# qatrack/test_settings.py, which is imported immediately before this file:
# DEBUG, NOTIFICATIONS_ON, DEFAULT_NUMBER_FORMAT, AD_CLEAN_USERNAME,
# HTTP_OR_HTTPS, REVIEW_BULK, TIME_ZONE, AUTHENTICATION_BACKENDS and the
# password hasher. Repeating any of them here just restates a value you
# already have - add a setting below only when you want to *differ* from it.

import os

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        # Defaults follow the naming used by
        # deploy/mysql/create_db_and_role.sql (user qatrack / password
        # qatrackpass / database qatrackplus). Every value can be overridden by
        # an environment variable, which is how CI configures itself - see
        # .github/workflows/ci.yml.
        #
        # NAME is the *application* database, not the test database. Django
        # derives the test database by prefixing 'test_', so this yields
        # test_qatrackplus. It previously read 'qatrackplus_test', which would
        # have produced test_qatrackplus_test; CI worked around that with a sed.
        #
        # NOTE: create_db_and_role.sql is a *production* script and deliberately
        # does not grant what testing needs - it grants only qatrackplus.*, so
        # the test database cannot be created. For a machine you intend to run
        # tests on, also run:
        #
        #     GRANT ALL ON test_qatrackplus.* TO 'qatrack'@'localhost';
        #     FLUSH PRIVILEGES;
        #
        'NAME': os.environ.get('QATRACK_DB_NAME', 'qatrackplus'),
        'USER': os.environ.get('QATRACK_DB_USER', 'qatrack'),
        'PASSWORD': os.environ.get('QATRACK_DB_PASSWORD', 'qatrackpass'),
        'HOST': os.environ.get('QATRACK_DB_HOST', 'localhost'),
        'PORT': os.environ.get('QATRACK_DB_PORT', '3306'),  # MySQL default
    }
}
DATABASES['readonly'] = DATABASES['default']

# Optional: pin the browser for every Selenium run, instead of choosing it
# per run on the command line. See "Setting Up Selenium Browser Testing" in
# docs/developer/guide.rst for what these do and for the one-off form.
# SELENIUM_BROWSER = 'chromium'    # 'firefox' is the default
# SELENIUM_HEADLESS = False        # watch the run in a real browser window
