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

try:
    from .local_test_settings import *  # noqa: F403,F401
except ModuleNotFoundError as e:
    # Only treat this as "the file is missing" if it is local_test_settings
    # itself that is absent - if it exists but fails to import something
    # else, let that error surface rather than masking it behind a
    # misleading "not found" message.
    if e.name != 'qatrack.local_test_settings':
        raise

    # Fall back to a disposable in-memory database, loudly.
    #
    # Silently passing - which is what this used to do - is the genuinely
    # dangerous option, because it leaves DATABASES as whatever
    # local_settings.py configured. That may be a real, shared or staging
    # database, and the test run would then write to it.
    #
    # In-memory SQLite is the one fallback that cannot do damage: no file,
    # no persistence, gone when the process exits. settings.py already does
    # exactly this when local_settings.py is absent under pytest (see the
    # _running_pytest branch there), so this makes the two sibling files
    # behave consistently instead of one falling back and the other not.
    #
    # Deliberately NOT copying deploy/dev/local_test_settings.memory.py into
    # place: writing a file as a side effect of running tests leaves an
    # artifact the developer silently owns and is later confused by - "why
    # is my Postgres config being ignored?" answered by a file they never
    # knowingly created. Creating those files is dev-quickstart's job, where
    # it is the stated purpose rather than a surprise.
    import warnings

    _no_test_settings_msg = (
        "qatrack/local_test_settings.py not found - falling back to a "
        "disposable in-memory SQLite database for this run. Nothing is "
        "persisted and no existing database is touched. To choose your own "
        "test database, copy a template from deploy/dev/ (for example "
        "local_test_settings.sqlite.py) to qatrack/local_test_settings.py, "
        "or run `make dev-quickstart`."
    )
    # Note this warning lands in pytest's end-of-run summary, which is easy
    # to miss. conftest.py raises the same thing as a config-time warning so
    # it also appears at the top of the run - printing to stderr here does
    # not work, since pytest captures output during settings import.
    warnings.warn(_no_test_settings_msg, RuntimeWarning, stacklevel=2)

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
    DATABASES['readonly'] = DATABASES['default']
