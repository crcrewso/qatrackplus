"""The Lint hook has to have looked at something.

`pre-commit run --all-files` reported `Lint ... Passed` on a commit whose
`backup_site.py` ruff rejected, and CI's Pre-Commit Test failed on exactly that
file minutes later. The cause was not the ruff version - both ends ran the
pinned 0.4.5 - but `exclude = [..., "*tmp*"]` in `pyproject.toml`. A
single-path pattern containing wildcards is matched against every component of
the *absolute* path, the checkout being verified lived under `/tmp`, and
`ruff-pre-commit` passes `--force-exclude`. So ruff was handed every file in
the tree, excluded all of them, printed

    warning: No Python files found under the given path(s)
    All checks passed!

and exited 0. Every "pre-commit clean" from that checkout meant nothing.

A hook that passes without inspecting anything is worse than no hook: it is
indistinguishable from a clean tree, and it reports success at precisely the
moment it has stopped working. So this asserts the thing the hook cannot
assert about itself - that this checkout's own source is reachable by the
linter as the hook invokes it - and it fails wherever that stops being true,
rather than in whichever CI job notices first.
"""

import pathlib
import subprocess
import sys
import tomllib

import pytest
from django.conf import settings

REPO_ROOT = pathlib.Path(settings.PROJECT_ROOT).parent

# How `ruff-pre-commit`'s `ruff` hook invokes it: the file list comes from
# pre-commit, and `--force-exclude` makes ruff honour `exclude` even for paths
# named explicitly. Without it, an explicitly named file is linted whatever
# `exclude` says - which is why running ruff by hand on the offending file
# reported the error that the hook had just passed over.
HOOK_ARGS = ['check', '--force-exclude', '--no-fix']

NOTHING_INSPECTED = 'No Python files found'


def ruff():
    """The linter from this environment, or None.

    ruff is a dev dependency, and the upgrade documentation tells a site
    administrator to run this suite against a `--no-dev` install, where it is
    absent. Skipping there is correct; passing silently would not be.
    """
    binary = pathlib.Path(sys.prefix) / ('Scripts' if sys.platform == 'win32' else 'bin')
    for name in ('ruff.exe', 'ruff'):
        candidate = binary / name
        if candidate.exists():
            return candidate
    return None


def run_ruff(*paths):
    found = ruff()
    if found is None:
        pytest.skip('ruff is not installed in this environment (a --no-dev install)')
    return subprocess.run(
        [str(found), *HOOK_ARGS, *[str(p) for p in paths]],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def excludes():
    with (REPO_ROOT / 'pyproject.toml').open('rb') as f:
        return tomllib.load(f)['tool']['ruff']['exclude']


# Three ordinary source files, in different applications, none of them in a
# directory `exclude` names. If the linter cannot see these, it cannot see
# anything that matters.
SUBJECTS = [
    'qatrack/qatrack_core/management/commands/backup_site.py',
    'qatrack/qa/views/perform.py',
    'qatrack/service_log/views.py',
]


@pytest.mark.parametrize('subject', SUBJECTS)
def test_the_linter_inspects_this_checkout(subject):
    path = REPO_ROOT / subject
    assert path.exists(), '%s has moved; pick another ordinary source file' % subject

    done = run_ruff(path)
    combined = done.stdout + done.stderr
    assert NOTHING_INSPECTED not in combined, (
        "ruff excluded %s when invoked as the pre-commit hook invokes it, so the Lint hook is "
        "passing without reading this checkout. Most likely a pattern in pyproject.toml's "
        "`exclude` matches a directory in the path this clone lives under: %r.\nruff said: %s"
        % (subject, excludes(), combined.strip())
    )


def test_a_real_error_is_reported_rather_than_excluded():
    """The test above only proves ruff looked. This proves it still reports."""
    offender = REPO_ROOT / 'qatrack' / 'qatrack_core' / 'tests' / 'zz_lint_gate_probe.py'
    offender.write_text('import datetime\nx = datetime.timezone.utc  # UP017\n', encoding='utf8')
    try:
        done = run_ruff(offender)
        combined = done.stdout + done.stderr
        assert NOTHING_INSPECTED not in combined, (
            'ruff excluded a file written into the test package itself: %s' % combined.strip()
        )
        assert done.returncode != 0 and 'UP017' in combined, (
            "ruff did not report UP017 on `datetime.timezone.utc`, so the gate would not have "
            "caught the error that reached CI. ruff said: %r (exit %d)"
            % (combined.strip(), done.returncode)
        )
    finally:
        offender.unlink(missing_ok=True)


def test_no_exclude_pattern_can_match_a_parent_directory():
    """The property that failed, stated directly.

    A pattern with no separator and no wildcard matches a path *within* the
    project. Add a wildcard and it is tried against every component of the
    absolute path as well, so an innocuous-looking name can disable the linter
    for everybody whose clone happens to sit under a directory of that name -
    `/tmp`, `/var/static`, a `media` mount point.
    """
    reckless = [pattern for pattern in excludes() if '*' in pattern and '/' not in pattern]
    assert not reckless, (
        "these `exclude` patterns are wildcards with no path separator, so ruff also tries them "
        "against the directories this checkout lives under, and a match silences the linter for "
        "the whole tree: %r. Drop the wildcards, or anchor the pattern with a `/`." % reckless
    )
