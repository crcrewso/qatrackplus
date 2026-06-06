Absolutely — below is a more **implementation-ready settings file set** you could adopt.

I’m optimizing for:

- **one facility-editable file**
- **shared base defaults**
- **minimal Django knowledge required for admins**
- **clean override order**
- **support for Windows Server, Fedora, Ubuntu**

---

# Proposed settings layout

```plain text
qatrack/
  settings/
    __init__.py
    base.py
    dev.py
    prod.py
    test.py
    site.example.py
    site.py              # local, facility-specific, not committed
```


## Responsibility split

- **`base.py`**: shared Django/project defaults
- **`dev.py`**: developer-only conveniences
- **`prod.py`**: production hardening defaults
- **`test.py`**: test runner settings
- **`site.py`**: the one editable local file for each facility
- **`site.example.py`**: template copy for administrators

---

# 1) `qatrack/settings/__init__.py`

This loader applies settings in the right order:

1. `base`
2. environment mode (`dev`, `prod`, or `test`)
3. `site` last, so facility overrides win

```python
import os

from .base import *  # noqa: F401,F403

ENVIRONMENT = os.environ.get("QATRACK_ENV", "dev").lower()

if ENVIRONMENT == "dev":
    from .dev import *  # noqa: F401,F403
elif ENVIRONMENT == "prod":
    from .prod import *  # noqa: F401,F403
elif ENVIRONMENT == "test":
    from .test import *  # noqa: F401,F403
else:
    raise RuntimeError(
        f"Unknown QATRACK_ENV={ENVIRONMENT!r}. Expected one of: dev, prod, test."
    )

try:
    from .site import *  # noqa: F401,F403
except ImportError as exc:
    raise ImportError(
        "Missing qatrack.settings.site. Copy site.example.py to site.py and edit it."
    ) from exc
```


---

# 2) `qatrack/settings/base.py`

This should contain the shared framework behavior and app wiring.

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR

# -----------------------------------------------------------------------------
# Core Django
DEBUG = False
SECRET_KEY = "replace-in-site-py"
ALLOWED_HOSTS = []

ROOT_URLCONF = "qatrack.urls"
WSGI_APPLICATION = "qatrack.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# Static/media defaults
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = PROJECT_ROOT / "static"
MEDIA_ROOT = PROJECT_ROOT / "media"
UPLOAD_ROOT = MEDIA_ROOT / "uploads"
TMP_UPLOAD_ROOT = UPLOAD_ROOT / "tmp"
TMP_REPORT_ROOT = MEDIA_ROOT / "reports"
LOG_ROOT = PROJECT_ROOT / "logs"

# -----------------------------------------------------------------------------
# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "qatrack.context_processors.site",
                "qatrack.context_processors.available_languages",
            ],
        },
    },
]

# -----------------------------------------------------------------------------
# Applications
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_extensions",
    "django_q",
    "django_comments",
    "formtools",
    "django_filters",
    "rest_framework",
    "rest_framework_filters",
    "rest_framework.authtoken",
    "listable",
    "qatrack.genericdropdown",
    "recurrence",
    "widget_tweaks",
    "dynamic_raw_id",
    "mptt",
    "django_mptt_admin",
    "qatrack.cache",
    "qatrack.accounts",
    "qatrack.units",
    "qatrack.qa",
    "qatrack.qatrack_core",
    "qatrack.notifications",
    "qatrack.contacts",
    "qatrack.issue_tracker",
    "qatrack.service_log",
    "qatrack.parts",
    "qatrack.faults",
    "qatrack.attachments",
    "qatrack.reports",
    "qatrack.form_utils",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "qatrack.middleware.login_required.LoginRequiredMiddleware",
    "qatrack.middleware.maintain_filters.FilterPersistMiddleware",
]

# -----------------------------------------------------------------------------
# Authentication / redirects
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/qc/unit/"
LOGOUT_REDIRECT_URL = LOGIN_URL

AUTHENTICATION_BACKENDS = [
    "qatrack.accounts.backends.QATrackAccountBackend",
]

SITE_ID = 1
SITE_NAME = "QATrack+"

# -----------------------------------------------------------------------------
# Messages / defaults
CONSTANT_PRECISION = 8
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# REST framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "qatrack.api.schemas.QATrackAutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.DjangoModelPermissions"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_FILTER_BACKENDS": ("rest_framework_filters.backends.RestFrameworkFilterBackend",),
}

# -----------------------------------------------------------------------------
# Caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "qatrack-default-cache",
    }
}

# -----------------------------------------------------------------------------
# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# -----------------------------------------------------------------------------
# App-specific defaults
PAGINATE_DEFAULT = 50
NHIST = 5
PING_INTERVAL_S = 5
USE_ISSUES = False
USE_SQL_REPORTS = False
PARTS_ALLOW_BLANK_PART_NUM = False
TESTPACK_TIMEOUT = 30
MAX_TESTS_PER_TESTLIST = 250
SELENIUM_BROWSER = ""
SELENIUM_FIREFOX_DRIVER_PATH = ""
SELENIUM_CHROMIUM_DRIVER_PATH = ""
SELENIUM_VIRTUAL_DISPLAY = False
```


---

# 3) `qatrack/settings/dev.py`

Development conveniences only.

```python
DEBUG = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    *INSTALLED_APPS,
    "debug_toolbar",
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *MIDDLEWARE,
]

# Easier local cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "qatrack-dev-cache",
    }
}
```


---

# 4) `qatrack/settings/prod.py`

Production hardening defaults.

```python
DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
```


---

# 5) `qatrack/settings/test.py`

Isolated test-friendly defaults.

```python
DEBUG = False

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "qatrack-test-cache",
    }
}

MIGRATION_MODULES = {
    # Optional: keep empty if you want real migrations in tests
}
```


---

# 6) `qatrack/settings/site.example.py`

This is the key file you’d ask facilities to copy to `site.py` and edit.

You asked for one file most users can touch, so I’d make this highly explicit.

```python
from pathlib import Path

# -----------------------------------------------------------------------------
# Facility identity
SITE_NAME = "Example Facility"
SITE_ID = 1
SITE_URL = "https://qatrack.example.org"

# -----------------------------------------------------------------------------
# Runtime
DEBUG = False
SECRET_KEY = "replace-me-with-a-random-secret-key"

ALLOWED_HOSTS = [
    "qatrack.example.org",
    "localhost",
    "127.0.0.1",
]

# -----------------------------------------------------------------------------
# Database
# Choose ONE backend and configure it here.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Example PostgreSQL configuration:
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": "qatrack",
#         "USER": "qatrack",
#         "PASSWORD": "replace-me",
#         "HOST": "localhost",
#         "PORT": "5432",
#     }
# }

# Example SQL Server configuration:
# DATABASES = {
#     "default": {
#         "ENGINE": "mssql",
#         "NAME": "qatrack",
#         "USER": "qatrack",
#         "PASSWORD": "replace-me",
#         "HOST": "localhost",
#         "PORT": "1433",
#         "OPTIONS": {
#             "driver": "ODBC Driver 18 for SQL Server",
#             "extra_params": "TrustServerCertificate=yes",
#         },
#     }
# }

# -----------------------------------------------------------------------------
# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = BASE_DIR / "static"
LOG_ROOT = BASE_DIR / "logs"
UPLOAD_ROOT = MEDIA_ROOT / "uploads"
TMP_UPLOAD_ROOT = UPLOAD_ROOT / "tmp"
TMP_REPORT_ROOT = MEDIA_ROOT / "reports"

# -----------------------------------------------------------------------------
# Email
EMAIL_HOST = "smtp.example.org"
EMAIL_PORT = 587
EMAIL_HOST_USER = "qatrack@example.org"
EMAIL_HOST_PASSWORD = "replace-me"
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "qatrack@example.org"

# -----------------------------------------------------------------------------
# Authentication
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/qc/unit/"
LOGOUT_REDIRECT_URL = LOGIN_URL

AUTHENTICATION_BACKENDS = [
    "qatrack.accounts.backends.QATrackAccountBackend",
]

# -----------------------------------------------------------------------------
# Feature flags
USE_SQL_REPORTS = False
USE_ISSUES = False
USE_ADFS = False

# Optional LDAP settings
# AUTHENTICATION_BACKENDS = [
#     "qatrack.accounts.backends.QATrackAccountBackend",
#     "django_auth_ldap.backend.LDAPBackend",
# ]
```


---

# 7) Windows / Fedora / Ubuntu notes

The settings file itself usually doesn’t need OS branching if you keep paths in `site.py`. But if you want a convenience pattern, you can document defaults like these:

## Windows Server
- `BASE_DIR = Path(r"C:\qatrackplus")` is effectively implied by install location
- logs/static/media should use Windows paths in `site.py`
- SQL Server ODBC driver setup is external to Python

## Fedora
- common install root: `/srv/qatrackplus`
- LDAP may need system packages like OpenLDAP dev headers
- SQL Server often needs `unixODBC` + Microsoft driver

## Ubuntu
- common install root: `/var/www/qatrackplus`
- LDAP and ODBC may also need native system packages
- Apache/mod_wsgi paths should match virtualenv + project root

---

# 8) Suggested `site.py` handling

I would not require facilities to edit `base.py`.  
Instead, the deployment instructions would say:

1. copy `site.example.py` to `site.py`
2. edit `site.py`
3. set `QATRACK_ENV=prod` for production-like deployments, or leave it as `dev` for local testing

That keeps the “one file to edit” promise intact.

---

# 9) One small improvement I’d recommend

For a more polished experience, add a tiny helper in `site.example.py` to fail fast if placeholders are left behind.

Example:

```python
def _ensure_not_placeholder(value: str, name: str) -> None:
    if "replace-me" in value:
        raise RuntimeError(f"{name} still contains a placeholder value")

_ensure_not_placeholder(SECRET_KEY, "SECRET_KEY")
_ensure_not_placeholder(EMAIL_HOST_PASSWORD, "EMAIL_HOST_PASSWORD")
```


That’s optional, but it helps facilities catch bad setups immediately.

---

# My practical recommendation

For your use case, I’d keep it very simple:

- **developers maintain `base.py`**
- **each facility edits only `site.py`**
- **`dev.py` / `prod.py` / `test.py` are optional wrappers**
- **avoid putting OS-specific branching in the admin-editable file unless absolutely necessary**

If you want, I can next turn this into:

1. a **drop-in migration plan** from the current settings file, or
2. a **single-file version** that’s even simpler for smaller facilities.