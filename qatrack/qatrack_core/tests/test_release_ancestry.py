"""The release-ancestry check's own tests.

`scripts/check_release_ancestry.py` needs the repository's tags, which a shallow clone does
not have, so the parts that decide anything are tested here with the tag list handed in. What
the real tags say is the workflow's job.
"""

import pytest

from scripts.check_release_ancestry import declared_version, excepted, tags_to_check, version_of

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


def test_the_line_is_every_earlier_release_of_the_same_major():
    assert tags_to_check(REAL_TAGS, (4, 0, 2)) == ['v4.0.0', 'v4.0.1', 'v4.0.2']


def test_a_release_the_branch_has_not_reached_is_not_required():
    """At 4.0.1, `v4.0.2` does not exist yet from this branch's point of view."""
    assert tags_to_check(REAL_TAGS, (4, 0, 1)) == ['v4.0.0', 'v4.0.1']


def test_another_major_line_is_not_a_promised_pull():
    """3.x to 4.x is a documented upgrade with steps, not a `git pull`."""
    assert 'v3.1.0' not in tags_to_check(REAL_TAGS, (4, 0, 2))
    assert tags_to_check(REAL_TAGS, (3, 1, 1)) == ['v3.1.0', 'v3.1.1']


def test_the_3_1_exception_is_scoped_to_the_3_1_line():
    assert excepted('v3.1.1', (3, 1, 1))
    assert excepted('v3.1.1', (4, 0, 2)) is None


def test_the_4_0_line_has_no_exception():
    """`v4.0.1` is the failure this check exists for. Excepting it would empty the check out."""
    for version in ((4, 0, 1), (4, 0, 2), (4, 0, 3)):
        assert excepted('v4.0.1', version) is None
