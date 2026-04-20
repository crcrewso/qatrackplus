# .ai — AI-Generated Artifacts

This folder contains planning documents and deployment configuration files produced during an AI-assisted modernisation session (April 20, 2026).

## Contents

```
.ai/
├── README.md                        ← this file
├── deploy/
│   └── apache/
│       ├── apache24_linux.conf      ← Apache 2.4 config for Linux (mod_wsgi daemon mode)
│       └── apache24_windows.conf   ← Apache 2.4 config for Windows (mod_wsgi / Waitress)
└── plans/
    ├── django42_migration_plan.md   ← Django 4.2 LTS hardening plan (current version)
    └── django52_migration_plan.md   ← Staircase upgrade plan: 4.2 → 5.0 → 5.1 → 5.2 LTS
```

## Canonical locations in the project

The generated files were also written to their canonical project locations:

| .ai file | Project file |
|----------|-------------|
| `deploy/apache/apache24_linux.conf` | `deploy/apache/apache24_linux.conf` |
| `deploy/apache/apache24_windows.conf` | `deploy/apache/apache24_windows.conf` |
| `plans/django42_migration_plan.md` | `docs/developer/django42_migration_plan.md` |
| `plans/django52_migration_plan.md` | `docs/developer/django52_migration_plan.md` |

## Session context

- **Project**: QATrack+ v4.0.0
- **Django version at session start**: 4.2 (pinned in `pyproject.toml`)
- **Python**: 3.12–3.13
- **OS targets**: Windows (SQL Server + Active Directory), Linux (MySQL / PostgreSQL)
- **Previous web server (Windows)**: CherryPy (`deploy/win/cherrypy_deploy.py`)
- **Previous web server (Linux)**: Apache mod_wsgi (`deploy/apache/apache24_daemon.conf`)
