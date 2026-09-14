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
DATABASES['readonly'] = DATABASES['default']

# Test-specific settings
NOTIFICATIONS_ON = False
DEFAULT_NUMBER_FORMAT = None
AD_CLEAN_USERNAME = None
HTTP_OR_HTTPS = "http"
REVIEW_BULK = True
TIME_ZONE = 'America/Toronto'

# Selenium browser configuration for testing.
#
# For a one-off run, both of these can also be set from the command line
# instead of edited here - e.g.:
#   SELENIUM_BROWSER=chromium SELENIUM_HEADLESS=False pytest -m selenium
# (see settings.py for exactly how each environment variable is read).
# Uncommenting below instead makes the choice stick across every run.
#
# SELENIUM_BROWSER selects which browser drives the Selenium tests -
# 'firefox' (the default) or 'chromium'. Whichever you install/have
# available, Selenium Manager (built into Selenium 4.6+) auto-detects it
# and downloads a matching driver on its own - no manual driver install or
# path configuration needed on any host. Only set
# SELENIUM_FIREFOX_DRIVER_PATH/SELENIUM_CHROMIUM_DRIVER_PATH (see
# settings.py) if you need to pin a specific driver binary instead.
# SELENIUM_BROWSER = 'firefox'
# SELENIUM_BROWSER = 'chromium'

# SELENIUM_HEADLESS = True (the default, inherited from settings.py) runs
# headlessly with no display server needed at all - works the same on a
# workstation, CI, or an agent sandbox. Uncomment to watch tests execute
# in a real, visible browser window instead (requires a real display).
# SELENIUM_HEADLESS = False

AUTHENTICATION_BACKENDS = ['qatrack.accounts.backends.QATrackAccountBackend']

# Customize any of the above settings as needed for your test environment
