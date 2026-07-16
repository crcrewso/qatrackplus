# AGENTS.md — AI Agent Guidance for QATrack+

This file gives AI coding agents the context they need to contribute effectively
to QATrack+, a free and open-source Django application for managing quality
control and maintenance activities at radiation therapy and diagnostic imaging
facilities. It is used in safety-critical clinical environments around the world.

---

## Who can use this file

This guidance applies equally to human developers using agentic AI tools
(GitHub Copilot, Claude Code, Cursor, etc.) and to fully automated AI agents
exploring or drafting changes in this repository.

---

## Project overview

| | |
|---|---|
| **Language** | Python 3.12 / 3.13 |
| **Framework** | Django 4.2 (LTS) |
| **Database** | PostgreSQL, MySQL, or MS SQL Server |
| **Package manager** | [uv](https://docs.astral.sh/uv/) (preferred) or pip |
| **Linter / formatter** | [ruff](https://docs.astral.sh/ruff/) |
| **Test runner** | pytest via `runtests.sh` or `python manage.py test` |
| **Docs** | Sphinx — `make docs` from repo root |
| **Target branch** | `Dev` (not `master`) |

---

## Repository layout

```
qatrack/        # Django project root; most application code lives here
  accounts/     # User accounts and authentication
  api/          # Django REST Framework API
  attachments/  # File-attachment handling
  contacts/     # Contact / notification system
  core/         # Core utilities, mixins, templatetags
  faults/       # Fault-logging application
  notifications/
  parts/        # Spare-parts tracking
  qa/           # QA test-list engine — the heart of the application
  reports/
  service_log/  # Service and maintenance logs
  units/        # Treatment-unit definitions
docs/           # Sphinx documentation (reStructuredText)
fixtures/       # Demo / seed data
requirements/   # Pinned requirement files (base, dev, docs)
runtests.sh     # Convenience test runner
```

---

## Getting started

```bash
# 1. Create a virtual environment and install all dependencies
uv sync --dev          # preferred
# or: pip install -r requirements/dev.txt

# 2. Provide local settings (database credentials, etc.)
cp qatrack/local_settings.example.py qatrack/local_settings.py
# edit qatrack/local_settings.py as needed

# 3. Apply migrations and load demo data
python manage.py migrate
python manage.py loaddata fixtures/demo_data.json

# 4. Run the development server
python manage.py runserver
```

---

## Linting and formatting

```bash
ruff check .          # lint
ruff format .         # auto-format
```

Configuration lives in `pyproject.toml` under `[tool.ruff]`.  
Line length is **120 characters**. Quote style is **single quotes**.  
Import ordering is enforced (`ruff` rule set `I`).

---

## Running the tests

```bash
bash runtests.sh
# or equivalently:
python manage.py test
# or with pytest directly:
pytest
```

Tests live next to the application code in `tests/` subdirectories inside each
Django app. Write or update tests for every functional change. Do not remove or
disable existing tests.

---

## Coding conventions

- Follow the style of the surrounding code.
- One logical change per commit; write clear imperative commit messages.
- Keep PRs focused — reviewers' time is limited.
- All PRs must target the `Dev` branch, **not** `master`.
- Fill in the pull request template completely (`.github/pull_request_template.md`).
- PRs that include tests, documentation updates, and a clear *why* are merged
  fastest.

---

## Documentation

Docs are built with Sphinx and live in `docs/`.

```bash
make docs           # from the repo root
# open docs/_build/html/index.html
```

Most pages use reStructuredText (`.rst`). When adding a new page, add it to
the relevant `toctree` directive in the section's `index.rst`.

---

## AI policy

### Agentic AI is encouraged

QATrack+ explicitly welcomes the use of agentic AI tools — GitHub Copilot,
Claude Code, Cursor, and similar assistants. These tools help developers
understand unfamiliar code, draft implementations, generate test cases, and
catch mistakes. The maintainer uses them too.

**Good uses for AI agents in this repository:**

- Exploring the codebase and explaining how a feature works.
- Drafting migrations, serializers, views, or tests for human review.
- Suggesting refactors or surfacing potential bugs.
- Writing or improving documentation and docstrings.
- Generating a first-pass implementation that a human then reads, tests, and
  revises.

### Direct AI-authored PRs are not accepted

This project does **not** accept pull requests submitted without meaningful
human review and understanding. This is not a rule against AI; it is a rule
about accountability.

QATrack+ is used in radiation therapy clinics where software defects can have
patient-safety implications. The maintainers do not have the resources to
perform the deep review that would be needed to compensate for a contribution
the author themselves does not fully understand. Every pull request must be
owned by a person who:

1. **Has read and understands the diff** — not just the summary, but the
   actual lines changed.
2. **Can explain the reasoning** behind each non-trivial decision if asked
   during review.
3. **Has run the tests locally** and confirmed they pass.
4. **Takes responsibility** for the correctness and safety of the change.

If you used an AI tool to help write the code, that is great — please say so
in the PR description. What is not acceptable is submitting AI-generated code
that you have not reviewed and do not understand.

> **In short:** AI as a tool, human as the author. PRs authored by AI
> agents acting autonomously, without a human reading and validating every
> line, will be closed without review.

---

## Getting help

- [GitHub Discussions](https://github.com/qatrackplus/qatrackplus/discussions)
- [QATrack+ Google Group](https://groups.google.com/g/qatrack)
- [Project wiki](https://github.com/qatrackplus/qatrackplus/wiki)
- Email: [medphys@crcrewso.ca](mailto:medphys@crcrewso.ca)
