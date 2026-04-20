# Documentation Audit — QATrack+ v4.0.0
**Generated with AI | Date: 2026-04-20**

---

## Critical Issues (HIGH)

| # | Category | File | Description |
|---|----------|------|-------------|
| 1 | Outdated | `docs/install/win.rst`, `docs/install/linux.rst` | Guides reference `git checkout v3.1.1.4`; current version is 4.0.0 |
| 2 | Inconsistency | `docs/install/win.rst:207-224` | DB engine documented as `sql_server.pyodbc`; pyproject.toml requires `mssql-django>=1.5` |
| 3 | Outdated | `deploy/win/local_settings.py:8` | Example settings use deprecated `sql_server.pyodbc` engine |
| 4 | Outdated | `docs/install/config.rst:28` | Refers to restarting `CherryPy Windows Service`; Apache configs exist but aren't documented |
| 5 | Broken Reference | `docs/install/config.rst:185-186` | BitBucket link to old repo — project is now on GitHub |
| 6 | Inaccuracy | `docs/developer/schema.rst:3-11` | Schema diagram is from v0.3.0 (ancient); current version is 4.0.0 |

---

## Major Issues (MEDIUM)

| # | Category | File | Description |
|---|----------|------|-------------|
| 7 | Outdated | `docs/install/win.rst:57-60` | References Python 3.9.X; pyproject requires Python >=3.12, <=3.13 |
| 8 | Outdated | `docs/install/linux.rst:13` | References Ubuntu 20.04 with Python 3.8; current requires 3.12+ |
| 9 | Missing | `docs/install/` | No v4.0.0-specific installation guide exists; all docs reference v3.1.1 |
| 10 | Missing | `docs/install/` | No upgrade path documented from v3.1.1.4 → v4.0.0 |
| 11 | Missing | `docs/install/config.rst` | No Windows Apache+mod_wsgi guide even though `deploy/apache/apache24_windows.conf` exists |
| 12 | Inaccuracy | `docs/release_notes.rst:1-20` | Shows "Unreleased" header; pyproject.toml and index.rst both declare version 4.0.0 |
| 13 | Incomplete | `docs/release_notes.rst:13` | Known issue about "Copy References & Tolerances" not cross-referenced in admin docs |
| 14 | Missing | `docs/install/` | No guidance on database backend selection for v4.0.0 (mssql-django vs psycopg etc.) |
| 15 | Missing | `docs/install/` | No documentation of new Apache architecture vs old CherryPy deployment |
| 16 | Incomplete | `docs/developer/guide.rst:60-90` | Developer guide doesn't explain transitioning from old pip-based workflow to uv |

---

## Minor Issues (LOW)

| # | Category | File | Description |
|---|----------|------|-------------|
| 17 | Outdated | `docs/install/linux.rst:15` | References Ubuntu 18.04 as supported (EOL April 2023) |
| 18 | Outdated | Upgrade guides (linux/win 030, 02X) | Python support stated as "3.7, 3.8 & 3.9" — outdated for v4.0.0 audience |
| 19 | Inaccuracy | `docs/install/win.rst:262` | CherryPy section unclear if it's current recommendation or legacy alternative |
| 20 | Missing | `docs/developer/guide.rst` | No mention of Apache deployment options in developer guide |
| 21 | Outdated | `docs/install/linux.rst:209` | References PostgreSQL 12 and Python 3.6-3.9 |
| 22 | Incomplete | `docs/developer/schema.rst:17-26` | Schema generation instructions reference old install method; should reflect uv workflow |

---

## Summary

| Severity | Count |
|----------|-------|
| High     | 6     |
| Medium   | 10    |
| Low      | 6     |
| **Total** | **22** |

---

## Priority Action Plan

1. **Create v4.0.0 install guides** for Linux and Windows (currently all guides target v3.1.1.4)
2. **Update all DB engine references** from `sql_server.pyodbc` → `mssql-django` (including `deploy/win/local_settings.py`)
3. **Document Apache deployment** as the supported web server; clarify CherryPy is legacy
4. **Add upgrade path** from v3.1.1.4 → v4.0.0
5. **Update Python version requirements** throughout from 3.8-3.9 → 3.12-3.13
6. **Replace BitBucket URLs** with GitHub equivalents throughout
7. **Update `release_notes.rst`** to mark v4.0.0 as released
8. **Regenerate and replace** the database schema diagram (currently v0.3.0)
