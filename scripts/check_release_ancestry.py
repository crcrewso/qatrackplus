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

Nothing caught either one, because nothing looked. This is what looks. Run it anywhere:

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
    """The release tags this branch must be pullable from, oldest first.

    The same major line, up to and including the version the tree declares. A tag from a later
    version is a release this branch has not reached, and one from another major line is an
    upgrade nobody is promised as a `git pull`.
    """
    wanted = []
    for tag in tags:
        version = version_of(tag)
        if version and version[0] == current[0] and version <= current:
            wanted.append((version, tag))
    return [tag for _, tag in sorted(wanted)]


def excepted(tag, current):
    """The reason this tag is not required on this line, or None."""
    return EXCEPTIONS.get(('%d.%d' % current[:2], tag))


def main(argv=None):
    tip = (argv or sys.argv[1:] or ['HEAD'])[0]
    current = declared_version((ROOT / 'qatrack' / 'settings.py').read_text(encoding='utf8'))
    tags = git('tag', '--list', 'v*').split()
    wanted = tags_to_check(tags, current)

    print('tree version %s, tip %s (%s)' % ('.'.join(str(p) for p in current), tip, git('rev-parse', '--short', tip).strip()))

    if not wanted:
        # Nothing to check is nearly always a shallow clone with no tags, which would otherwise
        # pass silently and make this check worthless exactly when it matters.
        print('FAIL: no vX.Y.Z tag of the %d.x line was found. Fetch the tags '
              '(`fetch-depth: 0` in CI) and run again.' % current[0])
        return 1

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

    if broken:
        print('\nFAIL: a site on %s cannot `git pull` onto this branch; it gets a divergent '
              'history instead.' % ', '.join(broken))
        print('The published upgrade pages promise that pull. To restore it without changing a '
              'single file, on this branch run:')
        for tag in broken:
            print('    git merge -s ours %s' % tag)
        print('which makes the tag reachable and leaves the tree exactly as it is.')
        return 1

    print('\nOK: every %d.x release up to %s can be pulled onto this branch.'
          % (current[0], '.'.join(str(p) for p in current)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
