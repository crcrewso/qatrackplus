"""Guard the two things that decide what the order-independence job measures.

The job shuffles the test order to find tests that depend on each other. Two
settings decide whether its answer means anything, and neither is visible in
the result:

1. **Which plugins are registered, and in which order.** Django's test runner
   promises every ``TestCase`` runs before every ``TransactionTestCase``, and
   pytest-django keeps that promise with a sort. Between two ``tryfirst`` hooks
   pluggy calls the last-registered first, so pytest-randomly registered last
   shuffles first and pytest-django's sort survives, while pytest-randomly
   registered first lets the sort happen and then undoes it. Entry-point
   discovery order is not the same on every host - measured on one tree at one
   seed, Windows gave 0 failures by default and Linux gave 2 - so an unpinned
   run is a different test on different machines. ``-p django -p randomly``
   pins it, and pins the job to independence *within* Django's guarantee.

2. **That the command the summary prints is the command that ran.** This file
   has already shipped a summary that did not match its own run: it reported
   ``Seed: `unknown` `` on every generated-seed failure, because ``-q``
   suppressed the header the seed was being read back out of. A reproduce line
   that omits a flag the run had is the same defect with a quieter symptom -
   the person who follows it gets a different order and cannot reproduce the
   failure they were sent to look at.

Neither property fails visibly when it is broken. The job still runs, still
goes green or red, and still looks like it measured order independence.
"""

import pathlib
import re

QATRACK = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = QATRACK.parent
WORKFLOW = REPO_ROOT / '.github' / 'workflows' / 'order-independence.yml'

# `-p django`, `-p randomly`, `-p no:randomly` - in the order they appear.
PLUGIN_FLAG = re.compile(r'-p\s+([\w:]+)')


def workflow_source():
    return WORKFLOW.read_text()


def pytest_invocations():
    """Every line of the workflow that runs pytest, or tells a human to.

    Both matter: one is what the job measures, the other is what the person
    reading the failure will run.
    """
    # The run step wraps with a trailing backslash, and the seed is on the
    # continuation line - so rejoin those before looking at anything.
    source = workflow_source().replace('\\\n', ' ')
    lines = [
        ' '.join(line.split())
        for line in source.splitlines()
        if 'pytest' in line and not line.lstrip().startswith('#')
    ]
    assert lines, 'no pytest invocation found in %s' % WORKFLOW
    return lines


class TestTheWorkflowIsThere:

    def test_the_job_exists_at_the_path_the_tests_below_assume(self):
        assert WORKFLOW.is_file(), '%s is missing' % WORKFLOW


class TestTheShuffleIsPinnedToOnePluginOrder:

    def test_something_actually_turns_the_shuffle_on(self):
        """Without this, every assertion below passes by the shuffle being gone."""
        assert any('-p randomly' in line for line in pytest_invocations()), (
            'nothing in %s enables pytest-randomly, so the job no longer '
            'shuffles anything' % WORKFLOW.name
        )

    def test_every_shuffled_invocation_names_django_before_randomly(self):
        for line in pytest_invocations():
            if '-p randomly' not in line:
                continue
            plugins = PLUGIN_FLAG.findall(line)
            assert 'django' in plugins, (
                'this line shuffles without naming pytest-django, so whether '
                "Django's TestCase-before-TransactionTestCase sort survives is "
                'left to the host: %s' % line
            )
            assert plugins.index('django') < plugins.index('randomly'), (
                'pytest-django must be registered before pytest-randomly, so '
                'the shuffle runs first and the sort survives: %s' % line
            )


class TestTheReproduceLineRunsWhatTheJobRan:

    def test_the_plugin_flags_are_identical_in_every_invocation(self):
        flags = {line: PLUGIN_FLAG.findall(line) for line in pytest_invocations()}
        distinct = {tuple(v) for v in flags.values()}
        assert len(distinct) == 1, (
            'the workflow runs pytest with more than one set of -p flags, so '
            'the command it prints for a human is not the command it ran: %s' % flags
        )

    def test_the_seed_is_passed_explicitly_everywhere(self):
        """The seed used to be read back out of pytest's output, which `-q` hid."""
        for line in pytest_invocations():
            assert '--randomly-seed' in line, (
                'a shuffled run without an explicit seed cannot be reproduced: %s' % line
            )


class TestAnOrdinaryRunIsStillDeterministic:

    def test_the_default_addopts_keep_the_shuffle_off(self):
        """pytest-randomly turns itself on as soon as it is installed.

        Adding it as a dev dependency silently turned a bare `pytest`, and all
        eight CI test jobs, into a different order every time with a fresh seed
        and no record of it - which is how CI came to fail once on a
        unique-constraint collision that no local run reproduced. The shuffle is
        meant to be asked for, and this job is what asks.
        """
        pyproject = (REPO_ROOT / 'pyproject.toml').read_text()
        addopts = re.search(r'^addopts\s*=\s*"([^"]*)"', pyproject, re.MULTILINE)
        assert addopts, 'no addopts found in pyproject.toml'
        assert '-p no:randomly' in addopts.group(1), (
            'addopts is %r; without `-p no:randomly` every bare pytest run and '
            'every CI job shuffles' % addopts.group(1)
        )
