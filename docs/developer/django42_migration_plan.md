# QATrack+ — Django 4.2 LTS Hardening Plan

Django **4.2** is already pinned in `pyproject.toml`.  
This plan makes the codebase *fully* compliant with 4.2 LTS — zero deprecation warnings, all broken APIs removed — so a future step-up to 5.x does not carry forward technical debt.

---

## Current State Snapshot

| Item | Value |
|------|-------|
| App version | 4.0.0 |
| Django pin | `==4.2` |
| Python | `>=3.12, <=3.13` |
| Test runner | pytest-django |
| Databases supported | SQLite, MySQL, PostgreSQL, SQL Server (mssql-django) |
| Windows web server | CherryPy (to be replaced — see Apache plan) |

---

## Phase 1 — Settings Hygiene

### 1.1 Remove `SEND_BROKEN_LINK_EMAILS`
- **File**: `qatrack/settings.py:23`
- **Action**: Delete the line. This setting was removed in Django 4.0; leaving it in generates `ImproperlyConfigured` warnings on startup.

### 1.2 Remove `USE_L10N`
- **File**: `qatrack/settings.py:100`
- **Action**: Delete the line. `USE_L10N=True` is the Django ≥ 4.0 default and the setting is a no-op. It is removed entirely in Django 5.0.

### 1.3 Confirm `DEFAULT_AUTO_FIELD`
- **File**: `qatrack/settings.py:104`
- **Status**: Already `'django.db.models.BigAutoField'`. ✅

### 1.4 Update `filterwarnings` in `setup.cfg`
- **File**: `setup.cfg` `[tool:pytest]`
- **Action**: Change the filter target from `RemovedInDjango31` to `RemovedInDjango50` to catch the next wave of deprecations during test runs.

---

## Phase 2 — Remove Deprecated APIs

### 2.1 Replace custom `JSONField` with `django.db.models.JSONField`
- **Files**: `qatrack/qatrack_core/fields.py`, `qatrack/qa/models.py`, `qatrack/service_log/models.py`
- **Action**:  
  1. Delete `qatrack/qatrack_core/fields.py`.  
  2. Replace all `from qatrack.qatrack_core.fields import JSONField` imports with `from django.db.models import JSONField`.  
  3. Generate and apply a migration for each affected model — the new built-in field stores JSON natively (PostgreSQL/MySQL) or as TEXT (SQLite/SQL Server), preserving existing data.
- **Risk**: Medium. SQL Server (mssql-django) supports `JSONField` from v1.1 onward. Verify the installed version.

### 2.2 Migrate SQL Server engine name in legacy `local_settings`
- **Files**: `deploy/win/local_settings.py`, `deploy/win/appveyor_mssql.py`
- **Action**: Replace `'ENGINE': 'sql_server.pyodbc'` with `'ENGINE': 'mssql'`. The `django-mssql-backend` / `mssql-django` package uses the `mssql` engine name. `sql_server.pyodbc` is the old unmaintained library.
- **Dependency**: Add `mssql-django>=1.4` to `pyproject.toml`; remove any `django-pyodbc-azure` or `django-mssql` pins.

### 2.3 Audit `re_path` aliases
- **Files**: `qatrack/api/*/urls.py` (and any other URL modules using `re_path as url`)
- **Status**: Already aliased correctly (`from django.urls import re_path as url`). ✅  
- **Recommended action**: Replace the alias with direct `re_path()` calls to make intent explicit and remove the alias in 5.x.

---

## Phase 3 — Dependency Updates (4.2-compatible)

| Package | Current constraint | Target | Notes |
|---------|-------------------|--------|-------|
| `django-crispy-forms` | `>=1.14.0,<2.0` | `>=2.0` | v2 required for Django 4.0+; add `crispy-bootstrap3` or `crispy-bootstrap5` as a separate pack |
| `djangorestframework` | `>=3.14.0` | `>=3.15` | 3.15 adds Django 4.2 explicit support |
| `djangorestframework-filters` | `>=1.0.0.dev2` | Pin to latest stable | dev2 is a pre-release; evaluate `drf-spectacular` as an alternative |
| `django-registration` | `>=3.2` | `>=3.4` | 3.4 supports Django 4.2 |
| `django-filter` | `>=23.0` | `>=24.0` | Latest stable |
| `django-auth-adfs` | `>=1.7.0` | `>=1.10.0` | Confirm ADFS token validation against 4.2 |

Run `uv lock --upgrade` and verify the full test suite after each dependency update.

---

## Phase 4 — Template Updates

### 4.1 Template tag `{% load staticfiles %}`
- **Action**: Replace any `{% load staticfiles %}` with `{% load static %}` (removed in Django 3.0, confirm none remain).

### 4.2 `{% url %}` and `{% with %}` usage
- **Action**: Run a codebase scan for any deprecated template tags flagged in test output.

---

## Phase 5 — Security Hardening

### 5.1 CSRF trusted origins
- **File**: `qatrack/settings.py`
- **Action**: Add `CSRF_TRUSTED_ORIGINS = ['https://YOUR_HOSTNAME_HERE']`. This setting is required in Django 4.0+ when the `Origin` header is present. Without it, AJAX POST requests from the app's own domain may fail.

### 5.2 `SECRET_KEY` rotation
- **File**: `qatrack/settings.py:43`
- **Action**: The default `SECRET_KEY` is hard-coded and public in the repo. Require `local_settings.py` to override it, and raise `ImproperlyConfigured` in settings if the default value is detected in production (`DEBUG=False`).

### 5.3 `ALLOWED_HOSTS` validation
- **Action**: Ensure no `local_settings.py` file leaves `ALLOWED_HOSTS = ['*']` in production configs.

---

## Phase 6 — Test Suite

1. Run `pytest --tb=short -q` and confirm **zero** `RemovedInDjango50Warning` or `DeprecationWarning` lines.
2. Run with each database backend (SQLite, PostgreSQL, MySQL, SQL Server) using the matching `local_settings` file.
3. Update `setup.cfg` filter: `error:.*RemovedInDjango50.*`

---

## Phase 7 — Apache Migration (Windows & Linux)

See `deploy/apache/apache24_linux.conf` and `deploy/apache/apache24_windows.conf`.

- **Linux**: Replace the existing `apache24_daemon.conf` with `apache24_linux.conf`.  
- **Windows**: Uninstall / disable the CherryPy Windows Service. Deploy `apache24_windows.conf`.

---

## Completion Criteria

- [ ] `pytest` passes with zero Django deprecation warnings
- [ ] `python -Wd manage.py check --deploy` reports no issues
- [ ] All `local_settings.py` files use `'ENGINE': 'mssql'` for SQL Server
- [ ] `SEND_BROKEN_LINK_EMAILS` and `USE_L10N` removed from `settings.py`
- [ ] Custom `JSONField` replaced by `django.db.models.JSONField`
- [ ] `CSRF_TRUSTED_ORIGINS` set
- [ ] Apache configs deployed on both platforms
