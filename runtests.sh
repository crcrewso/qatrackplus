#!/bin/bash
# Thin convenience wrapper around the project's real test runner.
#
# This script used to drive Django's own test runner via `manage.py test`
# under `coverage`. That bypassed the pytest configuration entirely: it
# ignored the GUI/Selenium auto-skip in conftest.py (so it tried to launch a
# real browser on any machine that ran it), and it still passed
# --omit='sqlserver_ado' for a package QATrack+ has not depended on in years.
#
# `make cover` is the maintained entry point for a coverage run; this script
# is kept as an alias for it so existing muscle memory and any local scripts
# keep working. Arguments are passed through to pytest, e.g.
#
#     ./runtests.sh -k test_login
#     ./runtests.sh --run-selenium
#
exec uv run pytest --cov-report term-missing --cov ./ "$@"
