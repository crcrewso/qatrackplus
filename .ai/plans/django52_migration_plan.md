# QATrack+ — Django 5.2 LTS Migration Plan

**Pre-requisite**: The Django 4.2 hardening plan (`django42_migration_plan.md`) must be completed first.  
Django 5.2 is an LTS release (April 2025, supported until April 2028).

---

## Strategy

The recommended path is a **staircase upgrade**:

```
4.2 LTS  →  5.0  →  5.1  →  5.2 LTS
```

Each intermediate step catches breaking changes early. Spend one sprint per step; the test suite is your safety net. Every breaking change listed in the official Django release notes must be addressed before moving to the next step.

---

## Phase 1 — 4.2 → 5.0

### Breaking changes in Django 5.0

#### 1.1 `USE_L10N` removed
- **Status**: Already removed in the 4.2 plan. ✅

#### 1.2 `CSRF_TRUSTED_ORIGINS` now requires full scheme
- **Status**: Added in the 4.2 plan with `https://` prefix. ✅

#### 1.3 `ForeignKey.validate()` signature changed
- **Action**: Search for overrides of `ForeignKey.validate()` across models; update signature to include the new `using` parameter.

#### 1.4 `django.utils.timezone.utc` alias removed
- **Action**: `grep -r "timezone.utc"` — replace with `datetime.timezone.utc`.

#### 1.5 `ModelAdmin.get_deleted_objects` signature change
- **Action**: Audit `admin.py` files for any overrides of `get_deleted_objects`.

#### 1.6 `BaseUserCreationForm` / `UserCreationForm` field order changed
- **Action**: If any custom auth forms subclass the built-in forms, re-test registration flows.

#### 1.7 Asynchronous ORM (opt-in)
- **Action**: No immediate change required, but note that sync ORM usage inside async views now emits warnings. This is a 5.0 feature, not a breaking change, but async-capable views should be refactored to use `aget()`, `afilter()`, etc. over time.

### Dependency updates for 5.0

| Package | Minimum for 5.0 |
|---------|----------------|
| `asgiref` | ≥ 3.7.1 |
| `djangorestframework` | ≥ 3.15.1 |
| `django-crispy-forms` | ≥ 2.1 |
| `django-filter` | ≥ 24.3 |
| `django-registration` | ≥ 3.4 |
| `django-auth-adfs` | ≥ 1.12.0 |
| `django-mptt` | ≥ 0.16 |
| `mssql-django` | ≥ 1.5 |

```bash
# In pyproject.toml — change pin:
"Django>=5.0,<5.1"
uv lock --upgrade
pytest
```

---

## Phase 2 — 5.0 → 5.1

### Breaking changes in Django 5.1

#### 2.1 `ModelAdmin.list_editable` validation tightened
- **Action**: Ensure no `list_editable` field that is also in `list_display_links`.

#### 2.2 `django.db.models.query.QuerySet.__class_getitem__` removed
- **Action**: Generic type hints on QuerySets (e.g., `QuerySet[MyModel]`) now use the standard `QuerySet[MyModel]` syntax via `__class_getitem__`. This is a no-op if you are not using type hints.

#### 2.3 `SelectDateWidget.years` type change
- **Action**: If any form code passes `years=` as a `range` object, convert to a list.

#### 2.4 Translation functions
- **File**: Review any custom translation calls — `gettext_lazy` is unaffected, but less-used helpers may have changed signatures.

### Dependency updates for 5.1

| Package | Minimum for 5.1 |
|---------|----------------|
| `Django` | `>=5.1,<5.2` |
| `djangorestframework` | ≥ 3.15.2 |
| `django-q2` | ≥ 1.10 |

```bash
"Django>=5.1,<5.2"
uv lock --upgrade
pytest
```

---

## Phase 3 — 5.1 → 5.2 LTS

### Breaking changes in Django 5.2

#### 3.1 `INSTALLED_APPS` ordering enforced more strictly
- **Action**: Verify `django.contrib.contenttypes` appears before apps that depend on it.

#### 3.2 `django.contrib.admin` jQuery version bump
- **Action**: Custom admin JS that depends on jQuery must be tested against the bundled version.

#### 3.3 `Meta.default_manager_name` validation
- **Action**: Run `manage.py check` — stricter validation will flag manager ordering issues.

#### 3.4 Python minimum is 3.10
- **Status**: Project already requires `>=3.12`. ✅

### Dependency updates for 5.2

| Package | Minimum for 5.2 | Notes |
|---------|----------------|-------|
| `Django` | `==5.2` | Pin to LTS |
| `djangorestframework` | ≥ 3.16 | Verify once released |
| `django-crispy-forms` | ≥ 2.3 | Verify once released |
| `django-mptt` | ≥ 0.16 | Confirm Django 5.2 compatibility |
| `django-dynamic-raw-id` | ≥ 4.1 | Confirm Django 5.2 compatibility |

```bash
"Django==5.2"
uv lock --upgrade
pytest
python -Wd manage.py check --deploy
```

---

## Phase 4 — Modernisation Opportunities (non-breaking)

These are not required for the version bump but significantly modernise the codebase and should be done during or immediately after the 5.2 upgrade sprint.

### 4.1 Replace custom `JSONField` (if not done in 4.2 plan)
- Replace `qatrack/qatrack_core/fields.py` custom `JSONField` with `django.db.models.JSONField`.
- Generate schema migrations. Native JSON storage on PostgreSQL and MySQL improves query performance.

### 4.2 Adopt `path()` over `re_path()`
- Migrate URL patterns that use simple string patterns (no regex) from `re_path()` to `path()`.
- This is a readability improvement; `re_path()` is not deprecated in 5.2.

### 4.3 Async views for I/O-bound endpoints
- Django 5.x ORM fully supports async. Migrate report generation and long-running API endpoints to `async def` views using `aget()` / `afilter()`.

### 4.4 `LoginRequiredMiddleware` (new in Django 5.1)
- Replace the custom `LoginRequired` decorator/mixin used across views with the new built-in middleware, and use `@login_not_required` on public views.
- **File**: `qatrack/middleware/` — review existing login middleware for overlap.

### 4.5 Database-level `GeneratedField` (new in Django 5.0)
- Evaluate whether any calculated model properties (e.g., `TestInstance` pass/fail flags) benefit from `GeneratedField` for database-side computation.

### 4.6 Facets in `ModelAdmin.list_filter` (new in Django 5.0)
- Add `show_facets = ShowFacets.ALWAYS` to high-traffic admin list views for instant filter counts.

### 4.7 Field groups / fieldsets rendering (new in Django 5.0)
- Use `Field(…, group=…)` in `ModelForm` definitions to replace manual `{% for field in form %}` template loops.

---

## Phase 5 — WSGI → ASGI (Optional, Post-5.2)

Django 5.x's ASGI support is production-ready. Migrating from `wsgi.py` to `asgi.py` enables:
- WebSocket support (real-time test result push to browsers)
- Async background tasks alongside `django-q2`

Steps:
1. Add `asgi.py` (already scaffolded by Django startproject for new projects).
2. Switch `WSGI_APPLICATION` to `ASGI_APPLICATION`.
3. Replace Apache mod_wsgi with `mod_wsgi` in ASGI mode **or** switch to **uvicorn** behind Apache as reverse proxy.
4. Update the Apache configs in `deploy/apache/` with `ProxyPass` to uvicorn.

---

## Full Dependency Compatibility Matrix

| Package | 4.2 | 5.0 | 5.1 | 5.2 |
|---------|:---:|:---:|:---:|:---:|
| djangorestframework | 3.14 | 3.15 | 3.15 | 3.16 |
| django-crispy-forms | 2.0 | 2.1 | 2.2 | 2.3 |
| django-filter | 23.x | 24.x | 24.x | 24.x |
| django-mptt | 0.14 | 0.15 | 0.16 | 0.16 |
| django-registration | 3.2 | 3.4 | 3.4 | 3.4 |
| django-auth-adfs | 1.7 | 1.10 | 1.12 | 1.12 |
| mssql-django | 1.3 | 1.4 | 1.5 | 1.5 |
| django-q2 | 1.8 | 1.9 | 1.10 | 1.10 |

> All versions above are minimums; always pin to the latest patch at the time of upgrade.

---

## Completion Criteria for 5.2

- [ ] `pyproject.toml` pins `Django==5.2`
- [ ] `pytest` passes with zero `DeprecationWarning` or `RemovedInDjango*` warnings
- [ ] `python -Wd manage.py check --deploy` reports no issues on all database backends
- [ ] All three intermediate pins (5.0, 5.1) were tested before reaching 5.2
- [ ] `LoginRequiredMiddleware` adopted (Phase 4.4)
- [ ] Custom `JSONField` fully replaced (Phase 4.1)
- [ ] `ASGI_APPLICATION` migration evaluated and scheduled (Phase 5)
