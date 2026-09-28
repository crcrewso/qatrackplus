# Test-specific settings for QATrack+ - PostgreSQL variant
#
# Copy to qatrack/local_test_settings.postgres.py and run
# `poe test-engine postgres`, or to qatrack/local_test_settings.py to make it
# your everyday choice.
#
# The connection details come from the environment, with defaults matching
# deploy/dev/compose.test-databases.yaml - so `poe test-databases-up` and this
# file agree without either being edited. Point them somewhere else by
# exporting the variables, or by editing deploy/dev/.env.
#
# Reading the port from the same variable the compose file publishes is
# deliberate: a hardcoded port here and a different one in the container is a
# failure whose only symptom is a port that never comes up.

import os

DEBUG = True
TEMPLATE_DBG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # Django creates test_<NAME> itself, so the user needs CREATE
        # DATABASE. NAME need not exist beforehand.
        'NAME': 'qatrackplus_test',
        'USER': os.environ.get('QATRACK_TEST_POSTGRES_USER', 'qatrack'),
        'PASSWORD': os.environ.get('QATRACK_TEST_POSTGRES_PASSWORD', 'qatrack-test-only'),
        'HOST': os.environ.get('QATRACK_TEST_POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.environ.get('QATRACK_TEST_POSTGRES_PORT', '5432'),
    }
}
# `readonly` must be a *copy* that mirrors `default`, not the same dict object.
# Django's test runner sets up every alias in DATABASES, so an alias which *is*
# `default` is created and flushed twice. With `:memory:` both names resolve to
# one database and the second pass is harmless, which is why this went unnoticed;
# file-backed, it is not. Measured 2026-11-01 on the GUI suite against a file:
# 35 failures, 34 errors and 106 occurrences of `attempt to write a readonly
# database`, with zero lock errors - the second setup leaves the shared file
# read-only for the connection the first one is still using.
#
# `TEST: {'MIRROR': 'default'}` is Django's own answer for a replica: no second
# test database is built, and `readonly` is routed to `default`'s connection.
DATABASES['readonly'] = dict(
    DATABASES['default'],
    TEST={**DATABASES['default'].get('TEST', {}), 'MIRROR': 'default'},
)

# Everything below is unchanged from the other templates in this directory.

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
