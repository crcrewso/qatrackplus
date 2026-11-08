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


class TestTheGuiTestsAreLeftOutTheCurrentWay:

    def test_no_invocation_uses_the_deprecated_marker_form(self):
        """`-m "not selenium"` still works, and warns, and goes away in 4.2.

        Plain pytest has skipped the GUI tests by default since #867, which is
        the whole point of that change - the marker expression needed quoting on
        every shell, and any *other* expression (`-m "not slow"`) used to start
        a real browser nobody asked for. A workflow that keeps telling people to
        write the deprecated form outlives the deprecation.
        """
        for line in pytest_invocations():
            assert 'not selenium' not in line, (
                '`-m "not selenium"` is deprecated for removal in 4.2; plain '
                'pytest already skips the GUI tests: %s' % line
            )


class TestAnOrdinaryRunIsStillDeterministic:
    """pytest-randomly turns itself on as soon as it is installed.

    Adding it as a dev dependency silently turned a bare `pytest`, and all
    eight CI test jobs, into a different order every time with a fresh seed and
    no record of it - which is how CI came to fail once on a unique-constraint
    collision that no local run reproduced, and how a later session came to
    read five shuffles of one tree as five different trees.

    This used to be held off with `-p no:randomly` in `addopts`, and these
    tests asserted that string. That is no longer the mechanism: the pin turned
    the plugin off outright, which also made the opt-in a usage error -
    `pytest --randomly-seed=1` exited 120 with `unrecognized arguments`,
    because the plugin that defines the option was not loaded. conftest.py now
    leaves the plugin loaded and switches off only its reordering, so
    `--shuffle` can switch it back on.

    What is asserted here is the invariant, not the implementation: an ordinary
    run is in source order, asking shuffles, and a shuffled run says which
    order it used.
    """

    @staticmethod
    def conftest():
        return (REPO_ROOT / 'conftest.py').read_text(encoding='utf-8')

    def test_addopts_no_longer_disables_the_plugin_outright(self):
        """Because that is what made `--randomly-seed` an error."""
        pyproject = (REPO_ROOT / 'pyproject.toml').read_text()
        addopts = re.search(r'^addopts\s*=\s*"([^"]*)"', pyproject, re.MULTILINE)
        assert addopts, 'no addopts found in pyproject.toml'
        assert '-p no:randomly' not in addopts.group(1), (
            "addopts is %r. `-p no:randomly` unloads the plugin, which takes "
            "`--randomly-seed` away with it - conftest.py switches the reordering "
            "off instead, and leaves the option available." % addopts.group(1)
        )

    def test_conftest_turns_the_reordering_off_unless_asked(self):
        source = self.conftest()
        assert "'--shuffle'" in source, (
            'conftest.py no longer offers --shuffle, so there is no way to ask for a '
            'shuffled run without knowing to write `-p randomly` first'
        )
        assert 'randomly_reorganize' in source, (
            "conftest.py no longer touches pytest-randomly's `randomly_reorganize`, so "
            'a bare `pytest` shuffles again'
        )
        assert re.search(
            r"config\.option\.randomly_reorganize\s*=\s*bool\(\s*config\.getoption\('--shuffle'\)\s*\)",
            source,
        ), (
            'the link between --shuffle and the reordering is not the single assignment '
            'this test can check; if it has been rewritten, re-read it and update this'
        )

    def test_a_shuffled_run_says_which_order_it_used(self):
        """`-q` eats the header pytest-randomly announces its seed in."""
        source = self.conftest()
        assert 'pytest_terminal_summary' in source, (
            'conftest.py no longer reports the seed in the terminal summary, so a '
            'shuffled failure cannot be repeated: `addopts` carries `-q`, which '
            "suppresses both pytest's header and `pytest_report_header`"
        )
        assert '--randomly-seed=%s' in source, (
            'the summary no longer prints the seed itself, which is the only part of it '
            'that lets somebody repeat the order'
        )

    def test_the_summary_line_pins_the_plugins_the_job_pins(self):
        """A seed alone is not an order: the registration order decides it too."""
        printed = re.search(r'Repeat it with: ([^\'"]*)', self.conftest())
        assert printed, 'conftest.py no longer prints a "Repeat it with:" line'
        job = {tuple(PLUGIN_FLAG.findall(line)) for line in pytest_invocations()}
        assert job == {tuple(PLUGIN_FLAG.findall(printed.group(1)))}, (
            'the summary tells a person to run %r, but the job runs pytest with %s, so '
            'on a host whose entry-point order differs the person gets a different '
            'order from the one that failed' % (printed.group(1), sorted(job))
        )

    def test_the_job_asks_for_the_shuffle_the_way_a_person_would(self):
        """The workflow is also the documentation for how to run this locally."""
        shuffled = [line for line in pytest_invocations() if '-p randomly' in line]
        assert shuffled, 'no invocation in the workflow enables pytest-randomly'
        for line in shuffled:
            assert '--shuffle' in line, (
                'the workflow enables the plugin with `-p randomly` but never asks for '
                'the shuffle with `--shuffle`, so conftest.py leaves the reordering off '
                'and the job measures the ordinary order: %r' % line
            )
