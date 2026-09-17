# Test-specific settings for QATrack+ - PostgreSQL variant
# Copy this file to qatrack/local_test_settings.py and customize as needed

import os

DEBUG = True
TEMPLATE_DBG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # Defaults follow the naming used by
        # deploy/postgres/create_db_and_role.sql (user qatrack / password
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
        # does not grant what testing needs - the role cannot create the test
        # database. For a machine you intend to run tests on, also run:
        #
        #     ALTER ROLE qatrack CREATEDB;
        #
        'NAME': os.environ.get('QATRACK_DB_NAME', 'qatrackplus'),
        'USER': os.environ.get('QATRACK_DB_USER', 'qatrack'),
        'PASSWORD': os.environ.get('QATRACK_DB_PASSWORD', 'qatrackpass'),
        'HOST': os.environ.get('QATRACK_DB_HOST', 'localhost'),
        'PORT': os.environ.get('QATRACK_DB_PORT', '5432'),  # PostgreSQL default
    }
}
DATABASES['readonly'] = DATABASES['default']

# Test-specific settings
NOTIFICATIONS_ON = False
DEFAULT_NUMBER_FORMAT = None
AD_CLEAN_USERNAME = None
HTTP_OR_HTTPS = "http"
REVIEW_BULK = True
TIME_ZONE = 'America/Toronto'

# Selenium: which browser, and whether it is visible. Either can come from
# the environment for a one-off run instead:
#   SELENIUM_BROWSER=chromium pytest --run-selenium           # bash/zsh
#   $env:SELENIUM_BROWSER='chromium'; pytest --run-selenium   # PowerShell
# Selenium Manager resolves the driver itself; settings.py has the variables
# for pinning a specific binary.
#
# SELENIUM_BROWSER = 'chromium'   # 'firefox' is the default
# SELENIUM_HEADLESS = False       # watch it run; needs a real display

AUTHENTICATION_BACKENDS = ['qatrack.accounts.backends.QATrackAccountBackend']

# Customize any of the above settings as needed for your test environment
