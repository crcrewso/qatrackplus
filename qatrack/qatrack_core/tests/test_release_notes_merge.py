"""release_notes.md is the one file every pull request edits in the same place.

Each PR adds its bullet directly under the heading for the release being
prepared, so two PRs conflict there regardless of the order they land in - and
the conflict carries no information, since both bullets are wanted. The repo
therefore marks the file `merge=union` in `.gitattributes`, which keeps both
sides.

Union has one sharp edge, and these tests guard it. It never conflicts, so if
one branch CORRECTS a bullet while another adds one, the corrected line and the
stale original both survive with nothing to flag it. The convention is that a
pull request only appends; corrections are their own commit on the release
branch. The second failure mode is structural and is checked here directly: when
two branches each open the same version's section, union keeps both headings.

`git check-attr` is the real check - the attribute has to be in effect, not
merely present in the file - and it is skipped where git is unavailable.
"""

import pathlib
import re
import subprocess

import pytest

QATRACK = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = QATRACK.parent
GITATTRIBUTES = REPO_ROOT / ".gitattributes"
RELEASE_NOTES = REPO_ROOT / "release_notes.md"

VERSION_HEADING = re.compile(
    r"^## (v[0-9][0-9a-zA-Z.\-]*)(?:\s+\S.*)?$", re.MULTILINE
)


class TestTheUnionDriverIsDeclared:

    def test_gitattributes_exists(self):
        assert GITATTRIBUTES.is_file(), "%s is missing" % GITATTRIBUTES

    def test_release_notes_is_marked_union(self):
        text = GITATTRIBUTES.read_text(encoding="utf-8")
        assert re.search(r"^release_notes\.md\s+merge=union\s*$", text, re.MULTILINE), (
            "release_notes.md is not marked `merge=union` in .gitattributes, so "
            "two pull requests that each add a bullet will conflict"
        )

    def test_git_agrees_the_attribute_is_in_effect(self):
        """Being in the file is not the same as being applied."""
        try:
            out = subprocess.run(
                ["git", "check-attr", "merge", "--", "release_notes.md"],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
            pytest.skip("git unavailable: %s" % exc)
        if out.returncode != 0:
            pytest.skip("not a git checkout: %s" % out.stderr.strip()[:120])
        assert out.stdout.strip().endswith("merge: union"), (
            "git reports %r for release_notes.md, not `merge: union`"
            % out.stdout.strip()
        )


class TestNoVersionHasTwoHeadings:
    """The one thing a union merge gets wrong that nobody would notice.

    Two branches each opening `## v4.1.0` is the normal case at the start of a
    release cycle, and union keeps both headings with the bullets split between
    them. The published notes then show the version twice.
    """

    def test_release_notes_exists(self):
        assert RELEASE_NOTES.is_file(), "%s is missing" % RELEASE_NOTES

    def test_there_are_headings_to_check(self):
        found = VERSION_HEADING.findall(RELEASE_NOTES.read_text(encoding="utf-8"))
        # Two at the time of writing - `v4.0.2` and `v4.0.0 Recent Fixes`, the
        # version optionally followed by a phrase. Older releases are not kept
        # in this file, they live in the published docs, so the floor is low on
        # purpose; it is here to catch the regex matching nothing at all.
        assert len(found) >= 2, (
            "only found %d version headings in release_notes.md, so the check "
            "below is not looking at what it thinks it is" % len(found)
        )

    def test_each_version_appears_once(self):
        found = VERSION_HEADING.findall(RELEASE_NOTES.read_text(encoding="utf-8"))
        duplicated = sorted({v for v in found if found.count(v) > 1})
        assert not duplicated, (
            "these versions have more than one `## ` heading in "
            "release_notes.md: %s. A union merge produces this when two "
            "branches each open the same section - keep the first and move the "
            "bullets under it." % ", ".join(duplicated)
        )
