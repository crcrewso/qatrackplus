I can draft the layout, but I **can’t directly save files into your project** from here.

What I *can* do is give you a ready-to-paste draft for a file in the `.ai` folder, for example:

``

```markdown
# Django settings structure proposal

## Goal

Provide a settings layout where:
- developers maintain the shared Django behavior
- each facility edits only one local settings file
- platform-specific differences stay mostly hidden
- deployments remain easy to reason about

---

## Recommended file layout
```
text
qatrack/
  settings/
    __init__.py
    base.py
    dev.py
    prod.py
    test.py
    site.py
```
### Meaning of each file

#### `base.py`
Shared project settings that should rarely change across facilities.

Contains:
- `INSTALLED_APPS`
- `MIDDLEWARE`
- `TEMPLATES`
- `ROOT_URLCONF`
- `WSGI_APPLICATION`
- localization settings
- shared logging defaults
- shared static/media defaults
- shared Django/REST framework settings
- shared feature flags with safe defaults

#### `site.py`
The one file most facilities edit.

Contains:
- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DATABASES`
- `EMAIL_*`
- `SITE_NAME`
- `SITE_URL`
- `MEDIA_ROOT`
- `STATIC_ROOT`
- `LOG_ROOT`
- `UPLOAD_ROOT`
- custom branding
- facility-specific auth/integration settings
- facility-specific feature toggles

#### `dev.py`
Optional developer-focused overrides.

Contains:
- debug toolbar
- local-only cache/database tweaks
- relaxed logging
- local email backend
- browser/test settings if needed

#### `prod.py`
Optional production-style overrides.

Contains:
- stricter security settings
- proxy/SSL settings
- logging level changes
- cache backend selection
- session/cookie hardening

#### `test.py`
Test-specific settings.

Contains:
- in-memory or isolated test database config
- fast cache backend
- reduced password validation
- disabled external integrations
- test-friendly email backend

---

## Suggested loading pattern

`qatrack/settings/__init__.py` should:
1. load `base.py`
2. load one environment layer such as `dev.py` or `prod.py`
3. load `site.py` last so local facility overrides win

Example precedence:
```
text
base.py
  -> dev.py / prod.py / test.py
    -> site.py
```
That way:
- the framework defaults come first
- runtime mode tweaks come next
- facility-specific edits always win last

---

## What a facility admin should edit

A facility admin should only need to edit `site.py`.

Typical values:
- hostname(s)
- database credentials
- email server
- file paths
- SSL/proxy assumptions
- feature flags
- facility branding
- login behavior
- third-party endpoints

They should not need to touch:
- app registration
- middleware
- routing
- serializers
- internal logging config structure
- Django internals

---

## Example `site.py` skeleton
```
python
# qatrack/settings/site.py

from pathlib import Path

# -----------------------------------------------------------------------------
# Site identity
SITE_NAME = "Example Facility"
SITE_URL = "https://qatrack.example.org"

# -----------------------------------------------------------------------------
# Runtime
DEBUG = False
SECRET_KEY = "replace-me-with-a-real-secret-key"

ALLOWED_HOSTS = [
    "qatrack.example.org",
    "localhost",
    "127.0.0.1",
]

# -----------------------------------------------------------------------------
# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "qatrack",
        "USER": "qatrack",
        "PASSWORD": "replace-me",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# -----------------------------------------------------------------------------
# Paths
BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = BASE_DIR / "static"
LOG_ROOT = BASE_DIR / "logs"
UPLOAD_ROOT = MEDIA_ROOT / "uploads"

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

AUTHENTICATION_BACKENDS = [
    "qatrack.accounts.backends.QATrackAccountBackend",
]

# -----------------------------------------------------------------------------
# Facility-specific toggles
USE_SQL_REPORTS = False
USE_ADFS = False
```
---

## Example `base.py` skeleton
```
python
# qatrack/settings/base.py

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # project apps here
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "qatrack.urls"
WSGI_APPLICATION = "qatrack.wsgi.application"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```
---

## Example `dev.py` skeleton
```
python
# qatrack/settings/dev.py

DEBUG = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS = [
    "debug_toolbar",
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]
```
---

## Example `prod.py` skeleton
```
python
# qatrack/settings/prod.py

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```
---

## Suggested documentation text for new deployers

### For admins
1. Copy `site.example.py` to `site.py`
2. Edit only `site.py`
3. Set database/email/paths/hosts
4. Run migrations
5. Collect static
6. Start the service

### For developers
1. Leave `base.py` alone unless adding framework-wide behavior
2. Put environment-specific changes in `dev.py`, `prod.py`, or `test.py`
3. Keep facility-specific values in `site.py`

---

## Why this structure works well for your project

It matches your deployment model because each facility can have its own:
- database
- email server
- file paths
- login behavior
- optional integrations
- branding

while the shared project code stays centralized and maintainable.

---

## Best next step

If you want, I can turn this into a more complete draft with:
- exact import logic for `__init__.py`
- a `site.example.py`
- a Windows/Linux path strategy
- and a migration plan from the current single-file settings layout
```


If you want, I can also draft this as a **more implementation-ready file set** with exact `python` code for each file instead of markdown documentation.