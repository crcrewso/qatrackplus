# Test-specific settings for QATrack+ - SQL Server variant
# Copy this file to qatrack/local_test_settings.py and customize as needed
#
# Requires the `mssql` extra: uv sync --extra mssql

DEBUG = True
TEMPLATE_DBG = True

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'USER': 'your_mssql_user',
        'PASSWORD': 'your_mssql_password',
        'HOST': 'hostname',
        'PORT': '1433',  # SQL Server default
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
        # Database Name not needed for test environments.
        # User must be created on the host server with admin and dbcreator
        # rights. If you'd rather use Windows-integrated auth instead of a
        # SQL login, remove USER/PASSWORD above and add:
        #     'Trusted_Connection': 'yes',
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
