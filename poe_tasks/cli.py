"""Entry points for the poe tasks that need logic. Run as ``python -m poe_tasks <verb>``.

How arguments arrive, measured with poe 0.49.0 (the version ``uv.lock`` pins):

* **Declared poe arguments reach this process as environment variables**, for a
  ``cmd`` task exactly as for a Python body: a positional or option under its
  declared ``name``, a boolean as the string ``True`` when given and absent when
  not. ``${name}`` templating in the ``cmd`` line also works for strings, and an
  omitted optional positional vanishes cleanly; a boolean templates as the word
  ``True``, which is why booleans are read from the environment here and never
  templated.
* **Anything after ``--`` on the poe command line is appended to the command**,
  so it arrives in ``sys.argv`` after whatever the ``cmd`` line put there.
* **A task that declares no arguments forwards everything** without ``--``.
  ``cover`` declares nothing for that reason, and parses its own.
* **A task that declares an argument refuses undeclared ones** unless they come
  after ``--``. ``poe test-engine sqlite -k foo`` is an error;
  ``poe test-engine sqlite -- -k foo`` works.
* **A caller's ``--`` leaks through a ``ref``** as a literal ``--`` on the
  command line. ``_split_extras`` strips one, so a mirror such as
  ``poe make-test -- -k foo`` behaves the same as ``poe make-test -k foo``.

Every verb runs from the repository root, which is where poe runs tasks.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

COMPOSE = ['docker', 'compose', '-f', 'deploy/dev/compose.test-databases.yaml']
CONTAINER_ENGINES = ('postgres', 'mysql', 'mssql')
ENGINES = ('sqlite', 'memory') + CONTAINER_ENGINES
BROWSERS = ('firefox', 'chromium', 'edge')

# module names to try, and the extra in pyproject.toml that provides them
DRIVERS = {
    'postgres': (('psycopg', 'psycopg2'), 'postgres'),
    'mysql': (('MySQLdb',), 'mysql'),
    'mssql': (('mssql',), 'mssql'),
}

DEV_TEMPLATES = [
    ('deploy/dev/local_settings.dev.py', 'qatrack/local_settings.py'),
    ('deploy/dev/local_test_settings.sqlite.py', 'qatrack/local_test_settings.py'),
    ('deploy/dev/local_test_settings.memory.py', 'qatrack/local_test_settings.memory.py'),
]
DEV_DB = pathlib.Path('db/default.db')

SUPERUSER_ENV = {
    'DJANGO_SUPERUSER_USERNAME': 'superuser',
    'DJANGO_SUPERUSER_PASSWORD': 'superuser',
    'DJANGO_SUPERUSER_EMAIL': 'superuser@example.com',
}

RETIRED = {
    'make-schema': (
        '`make schema` is RETIRED, and so is this mirror of it: it wrote the diagram '
        'under a version hardcoded in the Makefile, and exited 0 even when the render '
        'failed.\n\nUse instead:   uv run poe schema'
    ),
    'make-nginx-conf': (
        '`make nginx.conf` is not reproduced by poe: it writes the config as the invoking '
        'user and `sudo mv`s it into place, so the installed file is writable by www-data '
        '(measured on Ubuntu 24.04, 2026-11-04). poe carries no replacement; the '
        'deployment helpers left the task runner on 2026-11-06 to be validated in their own '
        'pull request.\n\nInstall nginx by hand as docs/install/linux.rst describes.'
    ),
    'make-supervisor-conf': (
        '`make supervisor.conf` is not reproduced by poe: it leaves the two supervisor '
        'configs owned by the invoking user, the same ownership bug as `make nginx.conf`. '
        'poe carries no replacement; the deployment helpers left the task runner on '
        '2026-11-06 to be validated in their own pull request.\n\nInstall supervisor by '
        'hand as docs/install/linux.rst describes.'
    ),
}


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------


def _split_extras(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split ``argv`` at the first literal ``--``: what poe templated, and what the caller appended.

    poe places ``-- extras`` after the ``cmd`` line's own words, and a ``ref`` passes a
    caller's ``--`` on literally, so the marker can be present once or not at all.
    """
    if '--' in argv:
        at = argv.index('--')
        return argv[:at], argv[at + 1 :]
    return argv, []


def _flag(name: str) -> bool:
    """A declared boolean poe argument: ``True`` in the environment when given, absent when not."""
    return bool(os.environ.get(name))


def _env(name: str) -> str:
    return (os.environ.get(name) or '').strip()


def _manage(*args: str, env: dict | None = None) -> int:
    return subprocess.call([sys.executable, 'manage.py', *args], env={**os.environ, **(env or {})})


def _pytest(*args: str) -> int:
    return subprocess.call([sys.executable, '-m', 'pytest', *args])


def _say(*lines: str) -> None:
    for line in lines:
        print(line)
    # Flushed, or a subprocess's output lands above these lines: it writes
    # straight to the terminal while these prints are still buffered.
    sys.stdout.flush()


# --------------------------------------------------------------------------
# cover [path] [--skip-covered] [pytest extras]
# --------------------------------------------------------------------------


def cover(argv: list[str]) -> int:
    """The suite with a coverage report; one task where there were four.

    ``cover`` was ``--cov ./``, ``cover-qatrack`` was ``--cov qatrack``, ``cover-module m``
    was ``--cov ./m m`` without ``--reuse-db`` (the one copy that had drifted), and
    ``cover-mo`` was ``term-missing:skip-covered``. Scope and report detail are
    parameters, so they are arguments now. The task declares nothing to poe so that
    ``poe cover qatrack/units -k foo`` forwards without ``--``; everything argparse does
    not recognise goes to pytest.

    The path is a filesystem path, not a dotted module: it goes to both ``--cov`` and
    pytest, and pytest given ``qatrack.qa`` collects nothing, reports no coverage and
    exits 4, which looks like a module with no tests.
    """
    own, extras = _split_extras(argv)
    parser = argparse.ArgumentParser(prog='poe cover', add_help=False)
    parser.add_argument('path', nargs='?', default=None)
    parser.add_argument('--skip-covered', action='store_true')
    args, unknown = parser.parse_known_args(own)
    report = 'term-missing:skip-covered' if args.skip_covered or _flag('skip_covered') else 'term-missing'
    cmd = ['--reuse-db', '--cov-report', report, '--cov', args.path or './']
    if args.path:
        cmd.append(args.path)
    return _pytest(*cmd, *unknown, *extras)


# --------------------------------------------------------------------------
# test-engine <engine> [--docker] [-- pytest extras]
# --------------------------------------------------------------------------


def test_engine(argv: list[str]) -> int:
    """Run the suite against one engine with that engine's settings swapped in, and put yours back.

    Refuses, before touching anything, if a backup from an earlier run is still here.
    try/finally restores on any Python-level exit, Ctrl-C included, but cannot run if
    the process is killed outright (SIGHUP from a closed terminal, a dropped SSH
    session, a power cut), and that leaves the real settings in the ``.bak``. Copying
    over it then destroys them, which is the one outcome worth refusing rather than
    reporting. The Makefile's own ``_test-engine`` only restored if the pytest line
    completed.

    With ``--docker`` (a declared boolean, so it arrives in the environment), the
    engine's throwaway server is started first and the shipped settings template is
    copied into place if you have no copy of your own. The driver is checked before
    the container starts, because starting SQL Server and then failing on a missing
    driver wastes a minute and reads like a broken task.
    """
    own, extras = _split_extras(argv)
    engine = own[0] if own else _env('engine')
    if engine not in ENGINES:
        _say('error: engine must be one of %s, got %r' % (', '.join(ENGINES), engine))
        return 2
    extras = own[1:] + extras

    if _flag('docker'):
        if engine not in CONTAINER_ENGINES:
            _say('error: %s needs no container - `poe test-engine %s` is already the whole job.' % (engine, engine))
            return 2
        code = _driver_check(engine)
        if code:
            return code
        code = _compose_up(engine)
        if code:
            return code
        _settings_from_template(engine)

    src = pathlib.Path('qatrack/local_test_settings.%s.py' % engine)
    live = pathlib.Path('qatrack/local_test_settings.py')
    backup = pathlib.Path('qatrack/local_test_settings.py.bak')

    if not src.exists():
        _say(
            'error: %s not found.' % src,
            'Create it first - see deploy/dev/local_test_settings.%s.py for a starting template.' % engine,
        )
        return 1
    if backup.exists():
        _say(
            'error: %s already exists - an earlier run was killed before it could put your settings back.' % backup,
            'Move it to %s, or delete it, then try again.' % live,
        )
        return 1

    had_existing = live.exists()
    if had_existing:
        shutil.copyfile(live, backup)
    shutil.copyfile(src, live)
    try:
        status = _pytest(*extras)
    finally:
        if had_existing:
            shutil.move(str(backup), str(live))
        else:
            live.unlink(missing_ok=True)
    return status


def _driver_check(engine: str) -> int:
    """Refuse early, and say which extra to install, if the engine's driver is missing.

    Without this the first use on a venv synced without the extra ends in Django's
    own message, "Error loading psycopg2 or psycopg module", under a traceback that
    names neither the extra nor the command that installs it.
    """
    modules, extra = DRIVERS[engine]
    if any(importlib.util.find_spec(name) is not None for name in modules):
        return 0
    _say(
        'Cannot test against %s: its database driver is not installed here.' % engine,
        '',
        'Tried to import: %s' % ', '.join(modules),
        '',
        'The driver is an optional extra, so a plain `uv sync` leaves it out:',
        '',
        '    uv sync --extra %s' % extra,
        '',
        'Then run this again. Nothing has been started, so there is no container to clean up.',
    )
    return 1


def _compose_up(engine: str = '') -> int:
    """Start one throwaway database service, or all of them, and wait until it answers.

    ``--wait`` is the point: SQL Server accepts connections roughly a minute after the
    container starts, and the compose file's healthchecks are what ``--wait`` waits on.
    The servers keep nothing (tmpfs, no volume), so ``down`` leaves nothing behind.
    """
    _say('starting %s, and waiting until it answers' % (engine or 'postgres, mysql and mssql'))
    return subprocess.call(COMPOSE + ['up', '-d', '--wait'] + ([engine] if engine else []))


def _settings_from_template(engine: str) -> None:
    """Put the shipped test-settings template in place, only if you have no copy.

    A developer who has made their own, pointing at a real server with real
    credentials, must not have it overwritten by a task that spells "docker" in its
    name. The template reads the same QATRACK_TEST_* variables the compose file sets.
    """
    mine = pathlib.Path('qatrack/local_test_settings.%s.py' % engine)
    template = pathlib.Path('deploy/dev/local_test_settings.%s.py' % engine)
    if mine.exists():
        _say('using your own %s, unchanged' % mine)
        return
    shutil.copyfile(template, mine)
    _say(
        'copied %s -> %s' % (template, mine),
        'It reads the same QATRACK_TEST_%s_* variables the compose file sets, so it' % engine.upper(),
        'matches the container just started. Edit or delete it as you like - it is',
        'gitignored, and this task will not touch it again now that it exists.',
    )


# --------------------------------------------------------------------------
# test-databases-up [engine] / test-databases-down [engine]
# --------------------------------------------------------------------------


def databases_up(argv: list[str]) -> int:
    own, _ = _split_extras(argv)
    return _compose_up(own[0] if own else _env('engine'))


def databases_down(argv: list[str]) -> int:
    """``down`` takes the whole project with its network; one service is stopped and
    removed with ``rm --stop --force`` instead, which leaves the others running."""
    own, _ = _split_extras(argv)
    engine = own[0] if own else _env('engine')
    _say('stopping %s' % (engine or 'postgres, mysql and mssql'))
    return subprocess.call(COMPOSE + (['rm', '--stop', '--force', engine] if engine else ['down']))


# --------------------------------------------------------------------------
# test-integration [-- pytest extras]
# --------------------------------------------------------------------------


def test_integration(argv: list[str]) -> int:
    """Provision a fresh sqlite database exactly as a deployment would, then test against it.

    Refuses, before touching anything, if this would provision the developer's own
    database: migrate/createcachetable/collectstatic/createsuperuser read
    ``local_settings.py``, while only pytest reads the ``local_test_settings.py`` this
    task writes its TEST name into. nsmela measured the consequence on 2026-10-08: a
    superuser/superuser account landed in a real development database while the tests
    ran somewhere else. Asking Django for the effective name is the only reliable
    check, because the value can come from any layer of the settings.

    Only this task points the test database at the provisioned one. The shipped
    template deliberately names a different file, because Django deletes a file-based
    test database before creating it and again at teardown.
    """
    _, extras = _split_extras(argv)
    db = pathlib.Path('db/default.db')
    db_bak = pathlib.Path('db/default.db.bak')
    kept = pathlib.Path('db/pytest_default.db')
    live = pathlib.Path('qatrack/local_test_settings.py')
    live_bak = pathlib.Path('qatrack/local_test_settings.py.bak')
    pathlib.Path('db').mkdir(exist_ok=True)

    effective = subprocess.run(
        [
            sys.executable,
            '-c',
            "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qatrack.settings');"
            'django.setup();'
            "from django.conf import settings; print(settings.DATABASES['default']['NAME'])",
        ],
        capture_output=True,
        text=True,
    )
    if effective.returncode != 0:
        _say(effective.stderr.strip() or 'could not read DATABASES from the settings')
        return 1
    # Compared as paths, not strings: the settings hold a posix-style name and
    # str(db) is backslashed on Windows.
    if pathlib.Path(effective.stdout.strip()) != db:
        _say(
            'error: this task provisions the database your settings point at, and that is',
            '         %s' % effective.stdout.strip(),
            'not %s. Continuing would migrate that database and leave a' % db,
            'superuser/superuser account in it, while the tests ran somewhere else.',
            'Point local_settings.py at %s before running this.' % db,
        )
        return 1

    stale = [p for p in (db_bak, live_bak) if p.exists()]
    if stale:
        _say(
            'error: a backup from an earlier run is still here:',
            *('  %s' % p for p in stale),
            'That run did not finish restoring. Put them back, or remove them, first.',
        )
        return 1

    had_db = db.exists()
    had_live = live.exists()
    if had_db:
        shutil.move(str(db), str(db_bak))
    if had_live:
        shutil.copyfile(live, live_bak)
    shutil.copyfile('deploy/dev/local_test_settings.sqlite.py', live)
    with live.open('a', encoding='utf-8') as fh:
        fh.write("\nDATABASES['default']['TEST']['NAME'] = 'db/default.db'\n")

    status = 1
    try:
        for step in (('migrate',), ('createcachetable',), ('collectstatic', '--noinput')):
            code = _manage(*step)
            if code:
                return code
        code = _manage('createsuperuser', '--noinput', env=SUPERUSER_ENV)
        if code:
            return code
        status = _pytest('--reuse-db', *extras)
    finally:
        # Keep the provisioned db for inspection, but only if it exists: provisioning
        # may have failed before the database was created.
        if db.exists():
            kept.unlink(missing_ok=True)
            shutil.move(str(db), str(kept))
            _say('provisioned database kept at %s' % kept)
        if had_live:
            shutil.move(str(live_bak), str(live))
        else:
            live.unlink(missing_ok=True)
        if had_db:
            shutil.move(str(db_bak), str(db))
            _say('restored your %s' % db)
    return status


# --------------------------------------------------------------------------
# test-order [seed] [-- pytest extras]
# --------------------------------------------------------------------------


def test_order(argv: list[str]) -> int:
    """The suite in a shuffled order, to catch tests that depend on each other.

    ``-p randomly`` is passed here rather than enabled for every run: ``poe test`` has
    to stay deterministic, because a failure you cannot reproduce from the command
    that produced it is worse than no failure. pytest-randomly prints the seed it
    chose; replaying that seed replays the order exactly.
    """
    own, extras = _split_extras(argv)
    seed = own[0] if own else _env('seed')
    if importlib.util.find_spec('pytest_randomly') is None:
        _say(
            'pytest-randomly is not installed in this environment.',
            '',
            'If the order-independence branch is in your tree:',
            '',
            '    uv sync --group dev',
            '',
            'Otherwise, for a one-off run without installing it:',
            '',
            '    uv run --with pytest-randomly pytest -p randomly',
        )
        return 1
    cmd = ['-p', 'randomly']
    if seed:
        cmd.append('--randomly-seed=%s' % seed)
        _say('Replaying seed %s.' % seed, '')
    else:
        _say(
            'New shuffle. pytest-randomly prints the seed it chose below; pass it',
            'back as `poe test-order <seed>` to run the same order again.',
            '',
        )
    return _pytest(*cmd, *own[1:], *extras)


# --------------------------------------------------------------------------
# test-gui-<mode> [browser] [-- pytest extras]
# --------------------------------------------------------------------------


def test_gui(argv: list[str]) -> int:
    """The GUI suite with SELENIUM_BROWSER taken from the browser argument, if any.

    The window mode comes from the calling task's ``env`` table, which is what the
    task name is choosing. With no browser given, SELENIUM_BROWSER is left alone
    entirely rather than set to a default: settings.py reads it from the environment
    and local_test_settings.py may override it, so leaving it unset is what lets a
    developer's own choice through.
    """
    own, extras = _split_extras(argv)
    browser = own[0] if own else _env('browser')
    if browser and browser not in BROWSERS:
        _say('error: browser must be one of %s, got %r' % (', '.join(BROWSERS), browser))
        return 2
    if browser:
        os.environ['SELENIUM_BROWSER'] = browser
    mode = 'visible' if os.environ.get('SELENIUM_HEADLESS') == 'False' else 'headless'
    if os.environ.get('SELENIUM_SLOW_MO'):
        mode += ', slowed to %ss between actions' % os.environ['SELENIUM_SLOW_MO']
    _say('GUI tests: %s, %s' % (browser or 'browser from your settings', mode))
    return _pytest('-m', 'selenium', *own[1:], *extras)


# --------------------------------------------------------------------------
# lint [--fix] [-- extras]
# --------------------------------------------------------------------------


def lint(argv: list[str]) -> int:
    """The pre-commit suite over every file; with ``--fix``, ruff's automatic lint fixes instead.

    CI pins pre-commit to 4.6.0 via ``uvx pre-commit@4.6.0``; here it is whatever the
    dev group resolved, which uv.lock also holds at 4.6.0. If the two ever disagree,
    the lockfile is the one to change. Formatting is deliberately not here: see
    ``format-changed``.
    """
    own, extras = _split_extras(argv)
    if _flag('fix') or '--fix' in own:
        own = [a for a in own if a != '--fix']
        return subprocess.call(['ruff', 'check', '.', '--fix', *own, *extras])
    return subprocess.call(['pre-commit', 'run', '--all-files', *own, *extras])


# --------------------------------------------------------------------------
# format-changed [--check]
# --------------------------------------------------------------------------


def _git(*args: str) -> list[str]:
    done = subprocess.run(('git',) + args, capture_output=True, text=True)
    return done.stdout.splitlines() if done.returncode == 0 else []


def _integration_base() -> str | None:
    """The commit this branch left, so the whole branch is covered, not only uncommitted work.

    The remotes are tried before the local branch because a local develop is the one
    most likely to be stale.
    """
    for ref in ('upstream/develop', 'origin/develop', 'develop'):
        found = _git('merge-base', 'HEAD', ref)
        if found:
            return found[0]
    return None


def changed_python_files() -> list[str]:
    base = _integration_base()
    paths: set[str] = set()
    if base:
        paths.update(_git('diff', '--name-only', '--diff-filter=ACMR', base))
    else:
        print('No develop to compare against; only uncommitted changes were considered.')
    paths.update(_git('diff', '--name-only', '--diff-filter=ACMR'))
    paths.update(_git('diff', '--name-only', '--diff-filter=ACMR', '--cached'))
    paths.update(_git('ls-files', '--others', '--exclude-standard'))
    # --diff-filter already drops deletions, but a path can still be gone by now,
    # and these two suffixes are what ruff format acts on.
    return sorted(p for p in paths if p.endswith(('.py', '.pyi')) and pathlib.Path(p).is_file())


def format_changed(argv: list[str]) -> int:
    """Format only the Python files this branch changed, never the whole repo.

    Repo-wide ``ruff format`` has never been applied, so it produces a large diff of
    unrelated files (see AGENTS.md). The list is worked out from git and printed,
    because the whole point is that it is not the whole repo.
    """
    own, _ = _split_extras(argv)
    checking = _flag('check') or '--check' in own
    files = changed_python_files()
    if not files:
        _say('No changed Python files to format.')
        return 0
    _say(
        '%s %d changed Python file(s), not the repo:' % ('Checking' if checking else 'Formatting', len(files)),
        *('  %s' % name for name in files),
    )
    return subprocess.call(['ruff', 'format', *(['--check'] if checking else []), *files])


# --------------------------------------------------------------------------
# check-migrations
# --------------------------------------------------------------------------


def check_migrations(argv: list[str]) -> int:
    """Report any model change that still needs a migration, and fail if there is one.

    Two invocations, because neither answers the whole question: plain ``--dry-run``
    prints the operations and always exits 0, so it cannot gate anything;
    ``--check --dry-run`` exits 1 when a migration is missing and prints nothing,
    which reads exactly like "no migrations needed".
    """
    manage = [sys.executable, 'manage.py', 'makemigrations', '--dry-run']
    listing = subprocess.run(manage, capture_output=True, text=True)
    sys.stdout.write(listing.stdout)
    sys.stderr.write(listing.stderr)
    if listing.returncode != 0:
        # makemigrations itself failed - a bad model, an import error - and that is
        # the answer, not a verdict about pending migrations.
        return listing.returncode
    status = subprocess.run(manage + ['--check'], capture_output=True, text=True)
    if status.returncode != 0:
        _say('', 'Pending migrations. They belong in this pull request, and the change', 'should be marked Breaking.')
    return status.returncode


def ci_reminder(argv: list[str]) -> int:
    _say(
        '',
        'Locally green. Still only run by CI:',
        '  - the suite on postgres / mysql / mssql   (poe test-engine <engine>)',
        '  - the suite on Windows                     (no local equivalent)',
        '  - the Selenium suite, firefox and chromium (poe test-gui-*)',
        '  - the Docker build-and-run check           (deploy/docker)',
    )
    return 0


# --------------------------------------------------------------------------
# dev-init / dev-clean
# --------------------------------------------------------------------------


def dev_init(argv: list[str]) -> int:
    """Create a fresh sqlite dev environment, refusing if one already exists.

    Checks everything before writing anything. If a later step fails, what this run
    created is removed again, so the next ``dev-init`` is not refused by the
    half-made environment this run left; only this run's files are removed, since
    every path was checked as absent first. ``db/`` itself stays: ``mkdir`` may have
    found it already there.
    """
    existing = [dst for _, dst in DEV_TEMPLATES if pathlib.Path(dst).exists()]
    if DEV_DB.exists():
        existing.append(str(DEV_DB))
    if existing:
        _say(
            'This already looks like a set up dev environment:',
            *('  %s' % p for p in existing),
            '',
            'dev-init will not write over any of it. Either remove what you do not',
            'want and run this again, or use `poe dev-reset` to discard all of it',
            'and start over.',
        )
        return 1

    created: list[pathlib.Path] = []
    for src, dst in DEV_TEMPLATES:
        shutil.copyfile(src, dst)
        created.append(pathlib.Path(dst))
        _say('created %s from %s' % (dst, src))
    pathlib.Path('db').mkdir(exist_ok=True)

    def undo() -> None:
        for path in created:
            path.unlink(missing_ok=True)
        DEV_DB.unlink(missing_ok=True)
        _say('', 'removed what this run created - fix the problem above and run', '`poe dev-init` again.')

    for step, env in (
        (('migrate',), None),
        (('createcachetable',), None),
        (('createsuperuser', '--noinput'), SUPERUSER_ENV),
    ):
        code = _manage(*step, env=env)
        if code:
            undo()
            return code
    _say('dev environment ready - log in as superuser / superuser')
    return 0


def dev_clean(argv: list[str]) -> int:
    for path in [dst for _, dst in DEV_TEMPLATES] + [str(DEV_DB)]:
        target = pathlib.Path(path)
        if target.exists():
            target.unlink()
            _say('removed %s' % path)
    return 0


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


def dump_data(argv: list[str]) -> int:
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out = 'qatrack-dump-%s.json' % stamp
    _say('writing %s' % out)
    return _manage('dumpdata', '-v1', '--indent=2', '--natural-foreign', '--natural-primary', '--output', out)


def generate_sample_data(argv: list[str]) -> int:
    """A database that looks like a working clinic.

    ``--no-input`` is deliberately not exposed: the command prompts before clearing,
    and nothing here should be a shorter way to do something irreversible than
    doing it by hand.
    """
    days = _env('days')
    clearing = _flag('clear')
    cmd = ['generate_sample_data']
    if days:
        cmd += ['--days', days]
    if clearing:
        cmd.append('--clear')
    _say(
        '%s %s days of sample data%s'
        % (
            'Clearing, then generating' if clearing else 'Generating',
            days or '90 (the default)',
            ' - the command will ask you to confirm the clear' if clearing else '',
        )
    )
    return _manage(*cmd)


# --------------------------------------------------------------------------
# schema (a release task)
# --------------------------------------------------------------------------


def schema(argv: list[str]) -> int:
    """Regenerate the distributed schema diagram, named for the minor line.

    The schema is identical across every 4.0.z, so one diagram per x.y is what is
    described. The version is read from the installed package metadata: it used to
    live in three places that disagreed, so ``poe schema`` and ``make schema`` wrote
    different files.

    Rendered to a staged file and only moved into place if it worked.
    django-extensions falls back to pydotplus when pygraphviz is not importable, and
    pydotplus fails by writing a zero-byte file and exiting 0, which is how the
    Makefile's target destroyed the committed 838 KB diagram and reported success.
    ``--pygraphviz`` is explicit so a missing dependency fails loudly. The staged
    file is created inside the output directory: on Windows the system temp
    directory is often on another drive, and a rename across drives fails.
    """
    minor_line = '.'.join(importlib.metadata.version('qatrackplus').split('.')[:2])
    out = pathlib.Path('docs/developer/images/qatrack_schema_%s.svg' % minor_line)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='.qatrack_schema-', suffix='.svg', dir=out.parent)
    os.close(fd)
    staged = pathlib.Path(tmp_name)
    try:
        code = _manage(
            'graph_models',
            '-a',
            '-g',
            '--pygraphviz',
            '-X',
            'Issue,IssueStatus,IssueType,IssuePriority,IssueTag',
            '-o',
            str(staged),
        )
        if code != 0:
            print('error: graph_models failed (exit %d); %s left untouched' % (code, out), file=sys.stderr)
            return code or 1
        if not staged.exists() or staged.stat().st_size == 0:
            print('error: graph_models produced an empty diagram; %s left untouched.' % out, file=sys.stderr)
            print('Is pygraphviz installed? `uv sync --dev` should provide it.', file=sys.stderr)
            return 1
        staged.replace(out)
    finally:
        staged.unlink(missing_ok=True)
    _say('wrote %s (%d bytes)' % (out, out.stat().st_size))
    return 0


# --------------------------------------------------------------------------
# retired <mirror>
# --------------------------------------------------------------------------


def retired(argv: list[str]) -> int:
    """A ``make-*`` mirror whose Makefile target is retired or not reproduced: say so, name the
    replacement, and fail, so a checklist or habit that still spells the old name is told."""
    own, _ = _split_extras(argv)
    name = own[0] if own else ''
    if name not in RETIRED:
        _say('error: no retirement notice for %r; known: %s' % (name, ', '.join(sorted(RETIRED))))
        return 2
    print(RETIRED[name], file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

VERBS = {
    'cover': cover,
    'test-engine': test_engine,
    'test-integration': test_integration,
    'test-order': test_order,
    'test-gui': test_gui,
    'databases-up': databases_up,
    'databases-down': databases_down,
    'lint': lint,
    'format-changed': format_changed,
    'check-migrations': check_migrations,
    'ci-reminder': ci_reminder,
    'dev-init': dev_init,
    'dev-clean': dev_clean,
    'dump-data': dump_data,
    'generate-sample-data': generate_sample_data,
    'schema': schema,
    'retired': retired,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] not in VERBS:
        print('usage: python -m poe_tasks <verb> [arguments]', file=sys.stderr)
        print('verbs: %s' % ', '.join(VERBS), file=sys.stderr)
        print('These are run by the poe tasks in poe_tasks/*.toml; `poe` lists those.', file=sys.stderr)
        return 2
    return VERBS[argv[0]](argv[1:])
