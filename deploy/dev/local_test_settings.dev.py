# Test-specific settings for QATrack+
# Copy this file to qatrack/local_test_settings.py and customize as needed

# Development settings
DEBUG = True
TEMPLATE_DBG = True

# SQLite example
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db/default.db',
    }
}

# SQL Server example
"""
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'USER': 'testuser',
        'PASSWORD': '123456abc*$',
        'HOST': 'hostname',
        'PORT': '1433', # SQL Server default
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
        'Trusted_Connection': 'yes',
        # Database Name not needed for test environments
        # User must be created on host server with admin and dbcreator rights
    }
}
"""

# PostgreSQL example
"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'devdb',
        'USER': 'postgres admin',
        'PASSWORD': 'postgres admin password',
        'HOST': 'hostname',
        'PORT': '5432', # PostgreSQL default
    }
}
"""



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

# Test-specific password hasher for faster testing
from django.contrib.auth.hashers import BasePasswordHasher  # noqa: E402


class SimplePasswordHasher(BasePasswordHasher):
    """A simple hasher inspired by django-plainpasswordhasher"""

    algorithm = "dumb"  # This attribute is needed by the base class.

    def salt(self):
        return ""

    def encode(self, password, salt):
        return "dumb$$%s" % password

    def verify(self, password, encoded):
        algorithm, hash = encoded.split("$$", 1)
        assert algorithm == "dumb"
        return password == hash

    def safe_summary(self, encoded):
        """This is a decidedly unsafe version.

        The password is returned in the clear.
        """
        return {"algorithm": "dumb", "hash": encoded.split("$", 2)[2]}

PASSWORD_HASHERS = ("qatrack.test_settings.SimplePasswordHasher",)

AUTHENTICATION_BACKENDS = ['qatrack.accounts.backends.QATrackAccountBackend']

# Customize any of the above settings as needed for your test environment
