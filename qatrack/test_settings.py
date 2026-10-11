import importlib.util

from django.contrib.auth.hashers import BasePasswordHasher

try:
    from .settings import *  # noqa: F403,F401
except ImportError:
    pass

try:
    from .local_settings import *  # noqa: F403,F401
except ImportError:
    pass

NOTIFICATIONS_ON = False
DEFAULT_NUMBER_FORMAT = None
DEBUG = False
SELENIUM_VIRTUAL_DISPLAY = False # Set to True to use headless browser for testing (requires xvfb)
AD_CLEAN_USERNAME = None
HTTP_OR_HTTPS = "http"
REVIEW_BULK = True
TIME_ZONE = 'America/Toronto'
LANGUAGE_CODE = "en"


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

# -----------------------------------------------------------------------------
# Safe defaults, so a test run needs no local_test_settings.py
#
# This file has already imported local_settings.py above, which in a real
# deployment names the *production* database - and settings.py ships
# `DATABASES = {}`, so without the defaults below the suite would run against
# whatever that deployment configured. On SQLite that is hidden, because Django
# substitutes an in-memory database for an unset TEST['NAME']; on PostgreSQL,
# MySQL or SQL Server it would connect to the real server and create and drop
# test_<name> there.
#
# So the database and the cache are pinned here to something local and
# disposable. local_test_settings.py is imported after this block and can still
# override any of it - these are defaults, not a lock.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        # Stated, not inferred. Django would otherwise substitute ':memory:'
        # silently for an unset TEST['NAME'], which means the database a test
        # run uses is not the one the settings appear to name.
        'TEST': {'NAME': ':memory:'},
    }
}

# SQL Explorer reads the 'readonly' connection (EXPLORER_CONNECTIONS), and
# settings.py adds it when USE_SQL_REPORTS is on. Redefining DATABASES above
# would otherwise drop it.
DATABASES['readonly'] = DATABASES['default']

# The default cache is DatabaseCache on 'qatrack_cache_table', which has to be
# created outside the migrations. Local memory needs nothing, so the suite runs
# without that table existing.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# A missing local_test_settings.py is fine - the defaults above are safe. A
# *broken* one is not, and must not be mistaken for a missing one: a bare
# `except ImportError: pass` swallows a failing import inside the file too,
# which would silently discard a developer's own test settings and run
# something else.
if importlib.util.find_spec('qatrack.local_test_settings') is not None:
    from .local_test_settings import *  # noqa: F403,F401
