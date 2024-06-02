from django.contrib.auth.hashers import BasePasswordHasher
import datetime
import os
import sys

NOTIFICATIONS_ON = False
DEFAULT_NUMBER_FORMAT = None
DEBUG = False
SELENIUM_USE_CHROME = False
SELENIUM_VIRTUAL_DISPLAY = False
AD_CLEAN_USERNAME = None
HTTP_OR_HTTPS = "http"
REVIEW_BULK = True
TIME_ZONE = 'America/Toronto'


# -----------------------------------------------------------------------------
# Database settings

# if you wish to override the database settings below (e.g. for deployment),
# please do so here or in a local_settings.py file
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))


# 
#        'NAME': ':memory:',

LOG_ROOT = os.path.join(PROJECT_ROOT, "..", "logs")
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3'
        # 'NAME': os.path.join(PROJECT_ROOT, '..', 'db/default.db'),   # db name Or path to database file if using sqlite3.
        'NAME' : ':memory:', # Use this for an in-memory database
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.S
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}


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

try:
    from .local_test_settings import *  # type: ignore # noqa: F403,F401
except ImportError:
    pass
