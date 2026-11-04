"""Fail when a site on an older release of this line cannot ``git pull`` onto this branch.

The published upgrade pages tell a reader on an older release to ``git fetch origin`` then
``git pull``, and promise that "you never name a version - a ``git pull`` is all that moves you
between them". That promise holds only while every earlier release tag of the line is an
ancestor of the branch the reader is tracking. When it is not, the reader gets
``fatal: Not possible to fast-forward``, or a merge with dozens of conflicted files, and their
site stays on the old release.

That is not hypothetical. It shipped twice:

* ``v4.0.1`` was not an ancestor of ``v4.0.2``; the two lines diverged at #825, and every
  Windows and Linux 4.0.1 site following the published page hit 22 conflicted files.
* ``v3.1.1`` is not an ancestor of ``releases/3.1`` either, which is the same mistake on a line
  that is now end of life (see ``EXCEPTIONS``).

Nothing caught either one, because nothing looked. This is what looks, in two parts:

* **within a line** - every ``vX.Y.Z`` tag must be an ancestor of the ``X.Y`` branch tip, so a
  site on any patch of a line can pull to the latest one;
* **between lines** - the newest release of the line immediately before this one must be an
  ancestor too, because that is the hop the upgrade pages document.

Release lines are allowed to diverge from each other in content - that is the point of a release
branch - so this checks reachability and nothing else. Run it anywhere:

    python scripts/check_release_ancestry.py

It needs the tags, so in CI the checkout must be unshallow (``fetch-depth: 0``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Only tags shaped exactly `vX.Y.Z` are releases of a line. The repository also carries
# release candidates (`v3.1.0RC2`), four-component tags (`v0.3.0.19`), differently cased ones
# (`V4.0.Beta.1`) and local branch backups (`bak/...`); none of those are something a site
# tracks, and guessing at them would make this check a nuisance rather than a gate.
RELEASE_TAG = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')

VERSION_IN_SETTINGS = re.compile(r'^VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)

# The release a line's upgrade pages start from, where it has been decided. A new line
# upgrades from one fixed patch of the line before - `*_upgrade_from_4_0_1.rst` and its
# predecessors are each written against one source version, not against a whole line - so the
# tag named here is the one that has to stay reachable. Unset, the newest release of the
# previous line is assumed, which is the natural floor and the strictest honest guess.
UPGRADE_FLOORS = {
    # '4.1': 'v4.0.2',   # set this when 4.1's upgrade pages name their z
}

# Lines whose history cannot be repaired any more, with the reason. An entry here is a
# statement that no site will ever pull that tag onto that line again - not a way to quiet a
# failure on a line that is still released from.
EXCEPTIONS = {
    # 3.1 reached end of life before the 4.0 line opened, and `v3.1.1` was tagged off a
    # history `releases/3.1` never took. Repairing it would mean touching a branch that no
    # supported site tracks.
    ('3.1', 'v3.1.1'): '3.1 is end of life; no supported site upgrades within it',
}


def git(*args, cwd=ROOT):
    """Run git and return stdout, or raise with git's own message."""
    done = subprocess.run(('git', *args), cwd=str(cwd), capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError('git %s failed: %s' % (' '.join(args), (done.stderr or done.stdout).strip()))
    return done.stdout


def version_of(tag):
    """(major, minor, patch) for a release tag, or None when the tag is not one."""
    found = RELEASE_TAG.match(tag)
    return tuple(int(p) for p in found.groups()) if found else None


def declared_version(settings_text):
    """The version the working tree claims, as (major, minor, patch).

    Raises when `VERSION` is missing or is not three numbers: a release check that cannot read
    the version has nothing to compare against and must say so rather than pass.
    """
    found = VERSION_IN_SETTINGS.search(settings_text)
    if not found:
        raise RuntimeError('no VERSION assignment found in qatrack/settings.py')
    parts = found.group(1).split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise RuntimeError('VERSION is %r, which is not a three-part release version' % found.group(1))
    return tuple(int(p) for p in parts)


def tags_to_check(tags, current):
    """The releases of this line that must be pullable onto it, oldest first.

    The same `X.Y` line, up to and including the version the tree declares. A later version is a
    release this branch has not reached. Another line is somebody else's branch: lines are
    allowed to diverge, and what they owe each other is the one hop below, which
    `previous_line_tag()` covers.
    """
    wanted = []
    for tag in tags:
        version = version_of(tag)
        if version and version[:2] == current[:2] and version <= current:
            wanted.append((version, tag))
    return [tag for _, tag in sorted(wanted)]


def previous_line_tag(tags, current):
    """The release this line's upgrade pages start from, or None.

    `UPGRADE_FLOORS` when the line has declared one; otherwise the newest release of the line
    immediately before this one.

    The upgrade pages document one hop between lines - 4.0.1 to 4.0.2 within a line, 4.0.2 to
    4.1 between them - and a hop is only a `git pull` if the tag it starts from is reachable.
    The newest release of that line is the floor those pages should name; anything older goes
    through it.
    """
    declared = UPGRADE_FLOORS.get('%d.%d' % current[:2])
    if declared:
        # Returned whether or not the repository has it: a floor naming a tag that does not
        # exist is a mistake to report, not a reason to check nothing.
        return declared
    best = None
    for tag in tags:
        version = version_of(tag)
        if version and version[:2] < current[:2] and (best is None or version > version_of(best)):
            best = tag
    return best


def excepted(tag, current):
    """The reason this tag is not required on this line, or None."""
    return EXCEPTIONS.get(('%d.%d' % current[:2], tag))


def main(argv=None):
    tip = (argv or sys.argv[1:] or ['HEAD'])[0]
    current = declared_version((ROOT / 'qatrack' / 'settings.py').read_text(encoding='utf8'))
    tags = git('tag', '--list', 'v*').split()
    wanted = tags_to_check(tags, current)

    print('tree version %s, tip %s (%s)' % ('.'.join(str(p) for p in current), tip, git('rev-parse', '--short', tip).strip()))

    if not [t for t in tags if version_of(t)]:
        # No release tag at all is nearly always a shallow clone, which would otherwise pass
        # silently and make this check worthless exactly when it matters.
        print('FAIL: no vX.Y.Z tag was found at all. Fetch the tags '
              '(`fetch-depth: 0` in CI) and run again.')
        return 1

    if not wanted:
        print('  (no %d.%d release yet, so there is nothing within this line to check)' % current[:2])

    broken = []
    for tag in wanted:
        reason = excepted(tag, current)
        if subprocess.run(('git', 'merge-base', '--is-ancestor', tag, tip), cwd=str(ROOT)).returncode == 0:
            print('  ok       %s is an ancestor' % tag)
        elif reason:
            print('  excepted %s is not an ancestor: %s' % (tag, reason))
        else:
            print('  BROKEN   %s is not an ancestor' % tag)
            broken.append(tag)

    previous = previous_line_tag(tags, current)
    if previous is not None and previous not in tags:
        print('  BROKEN   %s is named as this line\'s upgrade floor and is not a tag here' % previous)
        print('\nFAIL: UPGRADE_FLOORS names %r for the %d.%d line, and no such release tag exists. '
              'Correct the floor, or fetch the tags.' % (previous, current[0], current[1]))
        return 1
    if previous is None:
        print('  (no line before %d.%d, so nothing to come from)' % current[:2])
    elif excepted(previous, current):
        print('  excepted %s, the line before this one: %s' % (previous, excepted(previous, current)))
    elif subprocess.run(('git', 'merge-base', '--is-ancestor', previous, tip), cwd=str(ROOT)).returncode == 0:
        print('  ok       %s is an ancestor, so the line before this one can reach it' % previous)
    else:
        print('  BROKEN   %s is not an ancestor: the line before this one cannot reach this one' % previous)
        broken.append(previous)

    if broken:
        print('\nFAIL: a site on %s cannot `git pull` onto this branch; it gets a divergent '
              'history instead.' % ', '.join(broken))
        print('The published upgrade pages promise that pull. To restore it without changing a '
              'single file, on this branch run:')
        for tag in broken:
            print('    git merge -s ours %s' % tag)
        print('which makes the tag reachable and leaves the tree exactly as it is.')
        return 1

    print('\nOK: every %d.%d release up to %s can be pulled onto this branch, and so can the '
          'release the line before it ended on.' % (current[0], current[1], '.'.join(str(p) for p in current)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
