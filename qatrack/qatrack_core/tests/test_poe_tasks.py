"""The poe tasks, tested without poe.

The task definitions are read with tomllib; the logic behind them is Python in
``poe_tasks/cli.py``, imported and called here with the commands it shells out
to replaced by stand-ins, or run against a temporary tree with a fake
``manage.py``. That is enough to prove what each verb does to the files it
touches, which is where the bugs were.

**Provenance.** @nsmela offered the first version of this file on #868 on
13 Oct, with a table of what each test should check; the comment carrying it is
truncated on GitHub and the file never existed on a branch, so the tests were
reconstructed from his table. On 2026-11-06 the Python bodies left the TOML for
``poe_tasks/cli.py`` (his suggestion on the same pull request), and the tests
that ran bodies through ``python -c`` now call the module. What each one proves
is unchanged, and the module tests that were impossible against TOML strings
(argument splitting, the exact pytest command) are new.
"""

import os
import pathlib
import subprocess
import sys
import tomllib

import pytest
from django.conf import settings

from poe_tasks import cli

REPO_ROOT = pathlib.Path(settings.PROJECT_ROOT).parent

# The public, non-mirror task surface. Raising this is a review decision, not a
# side effect of adding a task: a task earns a public name when it composes more
# than one command, hides a trap, or encodes something a newcomer could not
# guess; a one-line alias of a manage.py command does not (see *Adding a new
# poe task* in the developer guide). The make-* mirrors go with the Makefile in
# the 4.1 cycle and are not counted; `_` helpers are hidden and not counted.
PUBLIC_TASK_CAP = 30


def load_tasks():
    """Every task, from every file pyproject.toml includes."""
    with open(REPO_ROOT / 'pyproject.toml', 'rb') as f:
        includes = tomllib.load(f)['tool']['poe']['include']
    tasks = {}
    for include in includes:
        with open(REPO_ROOT / include, 'rb') as f:
            tasks.update(tomllib.load(f).get('tasks', {}))
    return tasks


TASKS = load_tasks()


def public_tasks():
    return sorted(name for name in TASKS if not name.startswith(('_', 'make-')))


# --------------------------------------------------------------------------
# The shape of the surface
# --------------------------------------------------------------------------


def test_public_task_count_is_a_decision():
    """The ratchet. `poe` with no arguments prints these; the mirrors do not count."""
    names = public_tasks()
    assert len(names) <= PUBLIC_TASK_CAP, (
        '%d public tasks against a cap of %d. Adding one is fine when it earns its name '
        '(see the comment on PUBLIC_TASK_CAP); then raise the cap in the same change, '
        'deliberately. Current: %s' % (len(names), PUBLIC_TASK_CAP, ', '.join(names))
    )


def test_every_task_has_a_help_line():
    """`poe` prints it and the generated appendix is built from it; the docs build also fails without one."""
    missing = [name for name, task in TASKS.items() if isinstance(task, dict) and not task.get('help')]
    assert not missing, missing


def test_no_task_carries_a_python_body():
    """Logic belongs in poe_tasks/cli.py, run from a `cmd`.

    A body inside a TOML string could not take `-- extras`, was unescaped by the
    TOML parser before Python saw it (a lone `\\n` became a real newline), closed
    the string on a triple-quoted docstring, and was never linted. Two mirrors keep
    a POSIX `shell` body because they reproduce what the Makefile does; nothing
    else may.
    """
    bodies = [name for name, task in TASKS.items() if isinstance(task, dict) and 'shell' in task]
    assert sorted(bodies) == ['make-docs', 'make-dumpdata'], bodies
    python_bodies = [name for name, task in TASKS.items() if isinstance(task, dict) and task.get('interpreter')]
    assert python_bodies == [], python_bodies


def test_every_module_verb_the_tasks_name_exists():
    """A `cmd` naming a verb the module does not have fails at run time, not at edit time."""
    used = set()
    for task in TASKS.values():
        cmd = task.get('cmd', '') if isinstance(task, dict) else ''
        words = cmd.split()
        if words[:3] == ['python', '-m', 'poe_tasks']:
            used.add(words[3])
    assert used, 'no task runs the module - has the command line changed?'
    assert used <= set(cli.VERBS), used - set(cli.VERBS)


def test_cover_declares_no_poe_arguments():
    """So `poe cover qatrack -k foo` forwards without `--`.

    A task that declares an argument refuses undeclared ones unless they follow
    `--` (measured, poe 0.49.0), and coverage is the task people filter most.
    The module parses path and --skip-covered itself.
    """
    assert 'args' not in TASKS['cover'], TASKS['cover']['args']


def test_booleans_are_never_templated_into_a_command():
    """A boolean argument templates as the word `True` in a `cmd` (measured, poe 0.49.0).

    The module reads them from the environment instead, where poe puts every
    declared argument. A `${flag}` in a command line would hand pytest a literal
    `True`.
    """
    offenders = []
    for name, task in TASKS.items():
        if not isinstance(task, dict):
            continue
        booleans = [a['name'] for a in task.get('args', []) if a.get('type') == 'boolean']
        for flag in booleans:
            if '${%s}' % flag in task.get('cmd', ''):
                offenders.append((name, flag))
    assert not offenders, offenders


# --------------------------------------------------------------------------
# The module: arguments
# --------------------------------------------------------------------------


def test_split_extras_strips_one_marker():
    assert cli._split_extras(['qatrack', '-k', 'foo']) == (['qatrack', '-k', 'foo'], [])
    assert cli._split_extras(['sqlite', '--', '-k', 'foo']) == (['sqlite'], ['-k', 'foo'])
    # A caller's `--` leaks through a `ref` literally; one is stripped, a second is pytest's.
    assert cli._split_extras(['--', '-k', 'foo', '--', 'x']) == ([], ['-k', 'foo', '--', 'x'])


@pytest.fixture
def pytest_calls(monkeypatch):
    calls = []

    def fake(*args):
        calls.append(list(args))
        return 0

    monkeypatch.setattr(cli, '_pytest', fake)
    return calls


def test_cover_builds_the_four_old_commands_from_one(pytest_calls, monkeypatch):
    monkeypatch.delenv('skip_covered', raising=False)
    cli.cover([])
    cli.cover(['qatrack'])
    cli.cover(['qatrack/units'])
    cli.cover(['--skip-covered'])
    cli.cover(['qatrack/qa', '-k', 'test_x', '-x'])
    assert pytest_calls == [
        ['--reuse-db', '--cov-report', 'term-missing', '--cov', './'],
        ['--reuse-db', '--cov-report', 'term-missing', '--cov', 'qatrack', 'qatrack'],
        ['--reuse-db', '--cov-report', 'term-missing', '--cov', 'qatrack/units', 'qatrack/units'],
        ['--reuse-db', '--cov-report', 'term-missing:skip-covered', '--cov', './'],
        ['--reuse-db', '--cov-report', 'term-missing', '--cov', 'qatrack/qa', 'qatrack/qa', '-k', 'test_x', '-x'],
    ]


def test_test_gui_sets_the_browser_only_when_named(pytest_calls, monkeypatch):
    monkeypatch.delenv('SELENIUM_BROWSER', raising=False)
    monkeypatch.delenv('browser', raising=False)
    assert cli.test_gui([]) == 0
    assert 'SELENIUM_BROWSER' not in os.environ, 'omitting the browser must leave yours alone'
    assert cli.test_gui(['chromium', '--', '-k', 'test_x']) == 0
    assert os.environ['SELENIUM_BROWSER'] == 'chromium'
    assert pytest_calls == [['-m', 'selenium'], ['-m', 'selenium', '-k', 'test_x']]
    assert cli.test_gui(['safari']) == 2, 'an unknown browser is refused, not run as firefox'


def test_test_order_passes_the_seed_and_the_extras(pytest_calls, monkeypatch):
    monkeypatch.delenv('seed', raising=False)
    monkeypatch.setattr(cli.importlib.util, 'find_spec', lambda name: object())
    cli.test_order([])
    cli.test_order(['42', '--', '-k', 'foo'])
    assert pytest_calls == [['-p', 'randomly'], ['-p', 'randomly', '--randomly-seed=42', '-k', 'foo']]


def test_test_order_explains_when_pytest_randomly_is_missing(pytest_calls, monkeypatch, capsys):
    monkeypatch.setattr(cli.importlib.util, 'find_spec', lambda name: None)
    assert cli.test_order([]) == 1
    assert pytest_calls == []
    assert 'uv run --with pytest-randomly' in capsys.readouterr().out


# --------------------------------------------------------------------------
# test-engine: the developer's settings file
# --------------------------------------------------------------------------


@pytest.fixture
def engine_tree(tmp_path, monkeypatch, pytest_calls):
    """A tree with just enough in it for `test-engine sqlite` to run, as the cwd."""
    (tmp_path / 'qatrack').mkdir()
    (tmp_path / 'qatrack' / 'local_test_settings.sqlite.py').write_text(
        '# the engine template this run should swap in\n', encoding='utf-8'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('docker', raising=False)
    monkeypatch.delenv('engine', raising=False)
    return tmp_path


def test_test_engine_refuses_to_overwrite_a_stale_backup(engine_tree, capsys):
    """A killed run leaves the real settings in the .bak; copying over it loses them.

    try/finally restores on any Python-level exit, Ctrl-C included, but cannot
    run when the process is killed outright - SIGHUP from a closed terminal, a
    dropped SSH session. @nsmela reproduced the loss end to end on #868.
    """
    live = engine_tree / 'qatrack' / 'local_test_settings.py'
    backup = engine_tree / 'qatrack' / 'local_test_settings.py.bak'
    live.write_text('# what a later run swapped in\n', encoding='utf-8')
    backup.write_text('# THE DEVELOPER OWN SETTINGS\n', encoding='utf-8')

    assert cli.test_engine(['sqlite']) != 0
    assert 'already exists' in capsys.readouterr().out
    assert backup.read_text() == '# THE DEVELOPER OWN SETTINGS\n', 'the backup was overwritten'
    assert live.read_text() == '# what a later run swapped in\n', 'the live file was touched'


def test_test_engine_restores_the_original_after_a_run(engine_tree, pytest_calls):
    """The normal case, so the refusal above cannot be satisfied by refusing always."""
    live = engine_tree / 'qatrack' / 'local_test_settings.py'
    live.write_text('# mine\n', encoding='utf-8')

    swapped = {}

    def record(*args):
        swapped['content'] = live.read_text()
        return 0

    cli._pytest = record
    assert cli.test_engine(['sqlite', '--', '-k', 'foo']) == 0
    assert swapped['content'] == '# the engine template this run should swap in\n'
    assert live.read_text() == '# mine\n'
    assert not (engine_tree / 'qatrack' / 'local_test_settings.py.bak').exists()


def test_test_engine_restores_even_when_pytest_raises(engine_tree, monkeypatch):
    live = engine_tree / 'qatrack' / 'local_test_settings.py'
    live.write_text('# mine\n', encoding='utf-8')

    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, '_pytest', interrupted)
    with pytest.raises(KeyboardInterrupt):
        cli.test_engine(['sqlite'])
    assert live.read_text() == '# mine\n'
    assert not (engine_tree / 'qatrack' / 'local_test_settings.py.bak').exists()


def test_test_engine_leaves_no_settings_file_when_there_was_none(engine_tree):
    """And does not invent one: a developer with no local_test_settings.py had none."""
    assert cli.test_engine(['sqlite']) == 0
    assert not (engine_tree / 'qatrack' / 'local_test_settings.py').exists()


def test_test_engine_forwards_extras_to_pytest(engine_tree, pytest_calls):
    """The regression the move to a module fixes: `poe test-engine sqlite -- -k foo` filters."""
    cli.test_engine(['sqlite', '--', '-k', 'foo'])
    assert pytest_calls == [['-k', 'foo']]


def test_test_engine_says_which_template_is_missing(engine_tree, capsys):
    assert cli.test_engine(['mysql']) != 0
    assert 'local_test_settings.mysql.py' in capsys.readouterr().out


def test_test_engine_rejects_an_unknown_engine(engine_tree, capsys):
    assert cli.test_engine(['oracle']) == 2
    assert 'oracle' in capsys.readouterr().out


def test_test_engine_docker_refuses_an_engine_with_no_container(engine_tree, monkeypatch, capsys):
    monkeypatch.setenv('docker', 'True')
    assert cli.test_engine(['sqlite']) == 2
    assert 'needs no container' in capsys.readouterr().out


def test_test_engine_docker_checks_the_driver_before_starting_anything(engine_tree, monkeypatch, capsys):
    """Starting SQL Server and then failing on a missing driver wastes a minute and reads like a broken task."""
    monkeypatch.setenv('docker', 'True')
    monkeypatch.setattr(cli.importlib.util, 'find_spec', lambda name: None)
    started = []
    monkeypatch.setattr(cli, '_compose_up', lambda engine='': started.append(engine) or 0)
    assert cli.test_engine(['postgres']) == 1
    assert started == [], 'the container was started although the driver is missing'
    assert 'uv sync --extra postgres' in capsys.readouterr().out


def test_test_engine_docker_copies_the_template_only_when_you_have_none(engine_tree, monkeypatch, pytest_calls):
    monkeypatch.setenv('docker', 'True')
    monkeypatch.setattr(cli.importlib.util, 'find_spec', lambda name: object())
    monkeypatch.setattr(cli, '_compose_up', lambda engine='': 0)
    (engine_tree / 'deploy' / 'dev').mkdir(parents=True)
    template = engine_tree / 'deploy' / 'dev' / 'local_test_settings.postgres.py'
    template.write_text('# shipped template\n', encoding='utf-8')
    mine = engine_tree / 'qatrack' / 'local_test_settings.postgres.py'

    assert cli.test_engine(['postgres']) == 0
    assert mine.read_text() == '# shipped template\n'

    mine.write_text('# my real server\n', encoding='utf-8')
    assert cli.test_engine(['postgres']) == 0
    assert mine.read_text() == '# my real server\n', "a developer's own settings were overwritten"


# --------------------------------------------------------------------------
# dev-init: a failure must not block the next attempt
# --------------------------------------------------------------------------


@pytest.fixture
def dev_tree(tmp_path, monkeypatch):
    (tmp_path / 'qatrack').mkdir()
    (tmp_path / 'deploy' / 'dev').mkdir(parents=True)
    for name in ('local_settings.dev.py', 'local_test_settings.sqlite.py', 'local_test_settings.memory.py'):
        (tmp_path / 'deploy' / 'dev' / name).write_text('# template\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_dev_init_undoes_what_it_created_when_a_step_fails(dev_tree, capsys):
    """Otherwise the rerun refuses, which is the problem dev-init exists to fix.

    The settings files are copied before `migrate` runs. With nothing to undo
    them, a failed migrate left all three in place, and the next `dev-init`
    answered 'This already looks like a set up dev environment' and exited 1.
    """
    # A manage.py that fails, standing in for a migrate that cannot run.
    (dev_tree / 'manage.py').write_text('import sys\nsys.exit(3)\n', encoding='utf-8')

    assert cli.dev_init([]) == 3
    left = sorted(p.name for p in (dev_tree / 'qatrack').iterdir())
    assert left == [], 'dev-init left %s behind, so the rerun will refuse' % left

    # And the rerun gets as far as calling manage.py again, rather than
    # refusing up front - which is the whole point.
    assert cli.dev_init([]) == 3
    assert 'already looks like a set up dev environment' not in capsys.readouterr().out


def test_dev_init_still_refuses_an_environment_it_did_not_create(dev_tree, capsys):
    """The negative control: the undo must not weaken the up-front refusal."""
    (dev_tree / 'qatrack' / 'local_settings.py').write_text('# mine, already here\n', encoding='utf-8')

    assert cli.dev_init([]) == 1
    assert 'already looks like a set up dev environment' in capsys.readouterr().out
    assert (dev_tree / 'qatrack' / 'local_settings.py').read_text() == '# mine, already here\n'


def test_dev_init_runs_as_the_task_does(dev_tree):
    """The module as poe runs it: a subprocess from the repository's own interpreter."""
    (dev_tree / 'manage.py').write_text('import sys\nsys.exit(0)\n', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(REPO_ROOT)}
    result = subprocess.run(
        [sys.executable, '-m', 'poe_tasks', 'dev-init'],
        cwd=dev_tree,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'dev environment ready' in result.stdout
    assert (dev_tree / 'qatrack' / 'local_settings.py').read_text() == '# template\n'


# --------------------------------------------------------------------------
# The retired mirrors
# --------------------------------------------------------------------------


@pytest.mark.parametrize('name', sorted(cli.RETIRED))
def test_a_retired_mirror_refuses_and_names_the_replacement(name, capsys):
    assert cli.retired([name]) == 1
    err = capsys.readouterr().err
    assert 'RETIRED' in err or 'not reproduced' in err
    assert TASKS[name]['cmd'] == 'python -m poe_tasks retired %s' % name


def test_retired_knows_no_other_names(capsys):
    assert cli.retired(['make-test']) == 2


# --------------------------------------------------------------------------
# The Makefile analogs must delegate, not carry their own copy
# --------------------------------------------------------------------------


def test_mirror_delegates_to_a_guarded_task():
    """Every `make-test-*` analog is a `ref`, so it cannot drift.

    `make-test-integration` used to hold its own shell copy of the
    provisioning sequence, without the database guard or the TEST name, and
    the five engine analogs shared a `_test-engine` shell task with no
    stale-backup refusal. Running either after an interrupted run destroyed
    the developer's database or settings. A `ref` has nothing to drift from.
    """
    mirrors = {name: task for name, task in TASKS.items() if name.startswith('make-test-')}
    assert mirrors, 'no make-test-* tasks found - has the compat layer been renamed?'

    for name, task in sorted(mirrors.items()):
        ref = task.get('ref')
        assert ref, '%s is not a ref: %s' % (name, sorted(task))
        target = ref.split()[0]
        assert target in ('test-engine', 'test-integration'), (name, ref)
        assert 'shell' not in task, '%s carries its own body as well as a ref' % name


def test_the_shell_copy_is_gone():
    """`_test-engine` must not come back while the analogs are refs."""
    assert '_test-engine' not in TASKS


def test_the_four_coverage_mirrors_are_one_task_with_arguments():
    """`ref` carries arguments (measured, poe 0.49.0), so the Makefile's four spellings share `cover`."""
    assert TASKS['make-cover']['ref'] == 'cover'
    assert TASKS['make-cover-qatrack']['ref'] == 'cover qatrack'
    assert TASKS['make-cover-mo']['ref'] == 'cover --skip-covered'
    assert TASKS['make-cover-module']['ref'] == 'cover'
    assert 'cover-qatrack' not in TASKS and 'cover-mo' not in TASKS and 'cover-module' not in TASKS


# --------------------------------------------------------------------------
# The catalogue tasks
# --------------------------------------------------------------------------


def test_check_messages_can_fail():
    """`python manage.py check` cannot: qatrack.W010 is a Warning, and check exits 0.

    Measured on #868 with one translation added to fr/django.po and not
    compiled: `manage.py check` printed W010 and exited 0, while
    `manage.py check_translations` reported the catalogue and exited 1. A task
    that reports a problem and then reports success is worse than no task.
    """
    cmd = TASKS['check-messages']['cmd']
    assert 'check_translations' in cmd, cmd
    assert cmd.split()[-1] != 'check', 'back on `manage.py check`, which exits 0 for a Warning'


def test_translation_status_does_not_parse_msgfmt_again():
    """The msgfmt-parsing body is gone; what is left to assert is that it has not come back."""
    task = TASKS['check-messages']
    assert 'check_translations' in task.get('cmd', ''), task
    assert 'shell' not in task, 'check-messages has a body again - see the docstring'
    assert 'msgfmt' not in str(task), 'msgfmt is back in the task; see the docstring'


def test_update_messages_runs_the_private_extraction_first():
    assert TASKS['update-messages']['sequence'] == ['_extract-messages', 'compile-messages']
    assert 'extract-messages' not in TASKS, 'extraction is a step, not a job; it is private'


def test_the_autobuild_ports_are_each_what_their_runner_documents():
    """The two runners serve on different ports, and that is now deliberate.

    The Makefile serves on 8009 and the docs say 8008 four times, so the
    successor task is the one that is right. The Makefile is frozen until it
    goes in the 4.1 cycle, so the disagreement cannot be fixed by editing it -
    it is made visible instead.
    """
    assert TASKS['docs-serve']['args'][0]['default'] == '8008'
    makefile = (REPO_ROOT / 'Makefile').read_text(encoding='utf-8')
    assert '--port 8009' in makefile, "the Makefile's own autobuild port has moved"
    assert '--port 8009' in TASKS['make-docs-autobuild']['cmd'], "the mirror no longer reproduces the Makefile's port"


# --------------------------------------------------------------------------
# The Makefile is frozen, and poe carries both ways of working
# --------------------------------------------------------------------------


def test_the_makefile_does_not_depend_on_poe():
    """A Makefile recipe that calls poe drags the dev group into production.

    crane measured what that costs on Ubuntu 24.04: `make supervisor.conf` on a
    site synced `--no-dev` took the environment from 112 packages to 200,
    because `uv run poe` syncs the default groups first. Cody reversed the alias
    decision on 2026-11-05. NAMING poe is fine; CALLING it is not: an `@echo`
    that mentions poe starts no process, so the test looks at what the recipe
    *executes*.
    """
    offenders = []
    for line in (REPO_ROOT / 'Makefile').read_text(encoding='utf-8').splitlines():
        if 'poe' not in line.lower():
            continue
        stripped = line.strip().lstrip('@-+')
        if stripped.startswith('#') or stripped.startswith(('echo ', 'echo"')):
            continue
        offenders.append(line)
    assert not offenders, offenders


def test_a_retired_target_says_so_and_fails_rather_than_pretending():
    """Nothing in the suite runs `make`, so a retired target is exactly the kind of
    thing a well-meaning edit could quietly un-retire, restoring a known trap.

    `schema` is retired because it was broken twice over: it named the diagram
    from a version hardcoded in the Makefile, and it exited 0 even when the
    render failed. Three things are asserted, because any one alone could be
    true of a target that still silently does the wrong thing.
    """
    recipe = recipe_for('schema')
    assert 'graph_models' not in recipe, 'the retired schema target renders the diagram again: %r' % recipe
    assert 'poe schema' in recipe, 'the retired schema target does not name the task that replaces it'
    assert 'exit 1' in recipe, 'the retired schema target exits 0'


def recipe_for(target):
    """A target's recipe lines, without the comments above it."""
    text = (REPO_ROOT / 'Makefile').read_text(encoding='utf-8')
    body = text.split('\n%s:\n' % target, 1)[1]
    lines = []
    for line in body.splitlines():
        if line and not line.startswith(('\t', ' ')):
            break
        lines.append(line)
    return '\n'.join(lines)


def mirror_for(target):
    """The task name mirroring a Makefile target; poe forbids a dot in one."""
    return 'make-' + target.replace('.', '-')


def makefile_targets():
    """Every target the Makefile defines, in file order."""
    for line in (REPO_ROOT / 'Makefile').read_text(encoding='utf-8').splitlines():
        if not line or line[0].isspace() or line.startswith('#') or ':' not in line:
            continue
        name = line.split(':', 1)[0].strip()
        if name.startswith(('.', '_')) or '=' in name or ' ' in name:
            continue
        yield name


def test_every_makefile_target_has_a_mirror():
    """`poe make-<target>` only means anything if there is one for every target.

    `help` is exempt: it prints a hand-written list of Makefile targets, and
    `poe` with no arguments already lists every task.
    """
    missing = [t for t in makefile_targets() if t != 'help' and mirror_for(t) not in TASKS]
    assert not missing, missing


def test_every_mirror_names_a_target_that_exists():
    """A mirror of a target nobody has is a mirror nobody can check."""
    targets = set(makefile_targets())
    orphans = [name for name in TASKS if name.startswith('make-') and not any(mirror_for(t) == name for t in targets)]
    assert not orphans, orphans


def test_the_makefile_has_a_target_for_every_habit_it_used_to_serve():
    """A rewrite is the easy place to drop a target somebody's script calls."""
    makefile = (REPO_ROOT / 'Makefile').read_text(encoding='utf-8')
    for target in (
        'test',
        'test_simple',
        'test-sqlite',
        'test-memory',
        'test-postgres',
        'test-mysql',
        'test-mssql',
        'test-integration',
        'cover',
        'cover-mo',
        'cover-module',
        'cover-qatrack',
        'docs',
        'docs-autobuild',
        'dumpdata',
        'nginx.conf',
        'supervisor.conf',
        'schema',
        'run',
        'help',
    ):
        assert ('\n%s:' % target) in makefile, 'no %s target' % target


def test_every_mirror_that_delegates_points_at_a_task_that_exists():
    """A `ref` to a task that does not exist fails at run time, not at edit time."""
    missing = []
    for name, task in TASKS.items():
        if not name.startswith('make-') or not isinstance(task, dict):
            continue
        ref = task.get('ref')
        if ref and ref.split()[0] not in TASKS:
            missing.append((name, ref))
    assert not missing, missing
