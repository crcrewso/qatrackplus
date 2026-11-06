"""`pytest` is in source order; `pytest --shuffle` is not. Measured, not read.

The sibling tests in `test_order_independence_workflow.py` read `conftest.py`
and `pyproject.toml` as text, which is enough to catch the switch being removed
and not enough to catch it being wired up wrongly. These run pytest in a
subprocess and compare the orders it collects, which is the only way to know.

Why this is worth three subprocess runs: the plugin shuffles from the moment it
is installed, with a fresh seed and nothing said about it under `-q`. One CI
failure on a unique-constraint collision that no local run reproduced, and one
session that read five shuffles of a single tree as five different trees, came
out of that. The property these tests hold is that a plain run can be compared
with another plain run.
"""

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Any module with a decent number of tests in it; the point is the order they
# come back in, not what they are.
SUBJECT = 'qatrack/qa/tests/test_models.py'

# `-o addopts=` is deliberate. `addopts` carries `-q`, which collapses
# `--collect-only` to a count per file and hides the order - and overriding it
# here costs nothing, because nothing else in `addopts` affects collection. In
# an ordinary run it would be a trap: it replaces the whole string rather than
# adding to it, which is how a `-p no:randomly` once got dropped silently.
BASE = ['-o', 'addopts=', SUBJECT, '--collect-only', '-q', '-p', 'no:cacheprovider']


def collected(*extra):
    """The node ids pytest collects, in order."""
    done = subprocess.run(
        [sys.executable, '-m', 'pytest', *BASE, *extra],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    ids = [line.strip() for line in done.stdout.splitlines() if '::' in line]
    assert len(ids) > 20, (
        'collected %d tests from %s, which is too few to tell one order from another.\n'
        'stdout: %s\nstderr: %s' % (len(ids), SUBJECT, done.stdout[-600:], done.stderr[-600:])
    )
    return ids


@pytest.fixture(scope='module')
def plain():
    return collected()


def test_a_plain_run_is_the_same_order_every_time(plain):
    assert collected() == plain, (
        'two plain `pytest` runs collected the same tests in different orders, so no two '
        'runs of this suite can be compared with each other'
    )


def test_asking_for_a_shuffle_gets_one(plain):
    """Three tries, because a shuffle may coincidentally match source order."""
    shuffles = [collected('--shuffle') for _ in range(3)]
    assert any(order != plain for order in shuffles), (
        '--shuffle did not change the order in three attempts, so the flag is not '
        'reaching pytest-randomly and the order-independence job is measuring the '
        'ordinary order'
    )


def test_a_seed_makes_a_shuffle_repeatable(plain):
    """Otherwise a failure found by the job cannot be reproduced from its summary."""
    first = collected('--shuffle', '--randomly-seed=1')
    assert collected('--shuffle', '--randomly-seed=1') == first, (
        'the same seed gave two different orders, so the reproduction command the job '
        'prints does not reproduce anything'
    )
    assert first != plain, (
        'seed 1 collected the tests in source order, so this test cannot tell a working '
        'shuffle from a broken one - pick another seed'
    )


def test_the_seed_option_is_usable_without_knowing_to_load_the_plugin():
    """It exited 120 with `unrecognized arguments` while `addopts` unloaded it."""
    done = subprocess.run(
        [sys.executable, '-m', 'pytest', *BASE, '--randomly-seed=1'],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert 'unrecognized arguments' not in (done.stdout + done.stderr), (
        '`pytest --randomly-seed=1` is a usage error again, which means something has '
        'gone back to unloading the plugin instead of switching off its reordering'
    )
