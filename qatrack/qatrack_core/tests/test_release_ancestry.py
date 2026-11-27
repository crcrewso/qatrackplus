"""The release-ancestry check's own tests.

`scripts/check_release_ancestry.py` needs the repository's tags, which a shallow clone does
not have, so the parts that decide anything are tested here with the tag list handed in. What
the real tags say is the workflow's job.
"""

import subprocess
from unittest.mock import patch

import pytest

from scripts.check_release_ancestry import (
    UPGRADE_FLOORS,
    declared_version,
    excepted,
    main,
    previous_line_tag,
    tags_to_check,
    version_of,
)

# The repository's own tag list, abridged: release candidates, four-component tags, a
# differently cased beta and the local branch backups all sit alongside the releases.
REAL_TAGS = [
    'v0.3.0.19', 'v3.1.0', 'v3.1.0RC2', 'v3.1.1', 'v3.1.1.4', 'v4.0.0', 'v4.0.1', 'v4.0.2',
    'V4.0.Beta.1', '4.0.0', 'bak/0925-1001/selenium-headless',
]


def test_only_three_part_v_tags_are_releases():
    assert version_of('v4.0.1') == (4, 0, 1)
    for not_a_release in ('v3.1.0RC2', 'v0.3.0.19', 'V4.0.Beta.1', '4.0.0', 'bak/0925-1001/poe'):
        assert version_of(not_a_release) is None, not_a_release


def test_declared_version_reads_the_version_the_tree_claims():
    assert declared_version('DEBUG = True\nVERSION = "4.0.2"\n') == (4, 0, 2)


@pytest.mark.parametrize('settings_text', [
    'DEBUG = True\n',                 # no VERSION at all
    'VERSION = "4.0"\n',              # two parts
    'VERSION = "4.1.0rc1"\n',         # not three numbers
])
def test_an_unreadable_version_fails_rather_than_passing(settings_text):
    """A check that cannot read the version has nothing to compare against."""
    with pytest.raises(RuntimeError):
        declared_version(settings_text)


def test_the_line_is_every_earlier_release_of_the_same_line():
    assert tags_to_check(REAL_TAGS, (4, 0, 2)) == ['v4.0.0', 'v4.0.1', 'v4.0.2']


def test_a_release_the_branch_has_not_reached_is_not_required():
    """At 4.0.1, `v4.0.2` does not exist yet from this branch's point of view."""
    assert tags_to_check(REAL_TAGS, (4, 0, 1)) == ['v4.0.0', 'v4.0.1']


def test_another_line_is_not_part_of_this_one():
    """Release lines are allowed to diverge; what they owe each other is the hop below."""
    assert 'v3.1.0' not in tags_to_check(REAL_TAGS, (4, 0, 2))
    assert tags_to_check(REAL_TAGS, (3, 1, 1)) == ['v3.1.0', 'v3.1.1']


def test_a_line_with_nothing_released_yet_has_nothing_within_it_to_check():
    """4.1 before its first tag: the within-line rule is empty and the hop below is the check."""
    assert tags_to_check(REAL_TAGS, (4, 1, 0)) == []
    assert previous_line_tag(REAL_TAGS, (4, 1, 0)) == 'v4.0.2'


def test_the_hop_below_is_the_newest_release_of_the_previous_line():
    assert previous_line_tag(REAL_TAGS, (4, 0, 2)) == 'v3.1.1'
    assert previous_line_tag(['v1.0.0'], (1, 0, 0)) is None


def test_a_declared_floor_wins_over_the_newest_release_below():
    """4.1 upgrades from one fixed 4.0.z, which the pages name, so the check pins that one."""
    with patch.dict(UPGRADE_FLOORS, {'4.1': 'v4.0.1'}, clear=False):
        assert previous_line_tag(REAL_TAGS, (4, 1, 0)) == 'v4.0.1'


def test_a_declared_floor_that_does_not_exist_is_still_returned():
    """A floor naming a tag this repository has not got is a mistake to report.

    Returning None here would read as "no line below, nothing to check" and pass.
    """
    with patch.dict(UPGRADE_FLOORS, {'4.1': 'v4.0.9'}, clear=False):
        floor = previous_line_tag(REAL_TAGS, (4, 1, 0))
    assert floor == 'v4.0.9'
    assert floor not in REAL_TAGS


def test_the_3_1_exception_is_scoped_to_the_3_1_line():
    assert excepted('v3.1.1', (3, 1, 1))
    assert excepted('v3.1.1', (4, 0, 2)) is None


def test_the_4_0_line_has_no_exception():
    """`v4.0.1` is the failure this check exists for. Excepting it would empty the check out."""
    for version in ((4, 0, 1), (4, 0, 2), (4, 0, 3)):
        assert excepted('v4.0.1', version) is None


# main(), end to end, against a throwaway repository: the exit status and the repair it prints.

def run_git(repo, *args):
    subprocess.run(('git', *args), cwd=str(repo), check=True, capture_output=True)


def commit_version(repo, version):
    settings = repo / 'qatrack' / 'settings.py'
    settings.parent.mkdir(exist_ok=True)
    settings.write_text('VERSION = "%s"\n' % version)
    run_git(repo, 'add', '.')
    run_git(repo, 'commit', '-q', '-m', version)


@pytest.fixture
def repo(tmp_path):
    run_git(tmp_path, 'init', '-q', '-b', 'releases/4.0')
    run_git(tmp_path, 'config', 'user.email', 'test@example.com')
    run_git(tmp_path, 'config', 'user.name', 'test')
    run_git(tmp_path, 'config', 'commit.gpgsign', 'false')
    run_git(tmp_path, 'config', 'tag.gpgsign', 'false')
    commit_version(tmp_path, '3.1.1')
    run_git(tmp_path, 'tag', 'v3.1.1')
    commit_version(tmp_path, '4.0.0')
    run_git(tmp_path, 'tag', 'v4.0.0')
    return tmp_path


def test_a_line_whose_releases_are_all_reachable_passes(repo, capsys):
    commit_version(repo, '4.0.1')
    run_git(repo, 'tag', 'v4.0.1')
    assert main([], root=repo) == 0
    assert 'OK:' in capsys.readouterr().out


def test_a_release_tagged_off_the_line_fails_and_names_the_repair(repo, capsys):
    """The 4.0.1 shape: the tag sits on a history the branch never took."""
    run_git(repo, 'switch', '-q', '-c', 'side')
    commit_version(repo, '4.0.1')
    run_git(repo, 'tag', 'v4.0.1')
    run_git(repo, 'switch', '-q', 'releases/4.0')
    commit_version(repo, '4.0.2')
    assert main([], root=repo) == 1
    out = capsys.readouterr().out
    assert 'BROKEN   v4.0.1' in out
    assert 'git merge -s ours v4.0.1' in out
    assert 'allow-unrelated-histories' not in out, 'the histories share an ancestor, so the plain repair works'


def test_the_line_below_must_be_reachable_too(repo, capsys):
    run_git(repo, 'switch', '-q', '--orphan', 'releases/4.1')
    commit_version(repo, '4.1.0')
    assert main([], root=repo) == 1
    out = capsys.readouterr().out
    assert 'BROKEN   v4.0.0 is not an ancestor: the line before' in out
    # No common ancestor, so the plain repair would fail with "refusing to merge unrelated histories".
    assert 'git merge -s ours --allow-unrelated-histories v4.0.0' in out


def test_no_release_tags_at_all_fails(tmp_path, capsys):
    """A shallow clone has no tags; passing then would make the check worthless."""
    run_git(tmp_path, 'init', '-q')
    run_git(tmp_path, 'config', 'user.email', 'test@example.com')
    run_git(tmp_path, 'config', 'user.name', 'test')
    run_git(tmp_path, 'config', 'commit.gpgsign', 'false')
    commit_version(tmp_path, '4.0.2')
    assert main([], root=tmp_path) == 1
    assert 'no vX.Y.Z tag' in capsys.readouterr().out


def test_the_version_is_read_from_the_tip_not_the_checkout(repo, capsys):
    run_git(repo, 'switch', '-q', '-c', 'develop')
    commit_version(repo, '4.1.0')
    assert main(['releases/4.0'], root=repo) == 0
    assert 'version 4.0.0 (from releases/4.0)' in capsys.readouterr().out


def test_a_tag_cut_off_a_side_branch_fails_against_its_line(repo, capsys):
    """What the workflow runs on a tag push: the line's branch as the tip, the version from the tag."""
    run_git(repo, 'switch', '-q', '-c', 'side')
    commit_version(repo, '4.0.1')
    run_git(repo, 'tag', 'v4.0.1')
    assert main(['releases/4.0', '--version-from', 'v4.0.1'], root=repo) == 1
    assert 'BROKEN   v4.0.1' in capsys.readouterr().out
    run_git(repo, 'switch', '-q', 'releases/4.0')
    run_git(repo, 'merge', '-q', '--ff-only', 'side')
    assert main(['releases/4.0', '--version-from', 'v4.0.1'], root=repo) == 0


def test_a_pushed_tag_must_name_the_version_its_tree_declares(repo, capsys):
    """Otherwise `v4.0.2` on a tree saying 4.0.1 is never selected, and never checked."""
    commit_version(repo, '4.0.1')
    run_git(repo, 'tag', 'v4.0.2')
    assert main(['releases/4.0', '--version-from', 'v4.0.2', '--tag', 'v4.0.2'], root=repo) == 1
    assert 'v4.0.2 was pushed, but the tree it tags declares VERSION 4.0.1' in capsys.readouterr().out


def test_a_pushed_tag_that_names_its_version_is_checked_and_passes(repo, capsys):
    commit_version(repo, '4.0.1')
    run_git(repo, 'tag', 'v4.0.1')
    assert main(['releases/4.0', '--version-from', 'v4.0.1', '--tag', 'v4.0.1'], root=repo) == 0
    assert 'ok       v4.0.1 is an ancestor' in capsys.readouterr().out


@pytest.mark.parametrize('tag', ['v4.0.1RC1', 'v0.3.0.19', 'V4.0.Beta.1'])
def test_a_tag_that_is_not_a_release_is_skipped(repo, capsys, tag):
    run_git(repo, 'tag', tag)
    assert main(['releases/4.0', '--version-from', tag, '--tag', tag], root=repo) == 0
    assert 'is not a vX.Y.Z release tag' in capsys.readouterr().out
