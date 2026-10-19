"""Which translatable strings a change adds, counted once each.

Used by the Translation Impact CI step. Compares every regenerated catalogue
with the committed one it replaced and reports the message ids that are new.

Why this is not a `grep` over the diff, which is what it replaced: gettext
writes a long message as `msgid ""` followed by quoted continuation lines, so
`^\\+msgid "` matches only short ones, and the bare `msgid ""` has to be
filtered out because it is also the header's. Every long string - which is to
say every real validation message - was therefore missing from the count and
from the report. Comparing catalogues as catalogues has no such blind spot.

Usage:

    new_translatable_strings.py <locale-dir> <previous-dir>

`previous-dir` holds the committed catalogues as `<locale>.po`. Prints the
count on the first line and one message per line after it.
"""

import pathlib
import sys

import polib


def new_msgids(locale_dir, previous_dir):
    """Message ids present in the regenerated catalogues and not in the committed ones.

    De-duplicated across locales: `makemessages --all` adds the same string to
    every catalogue, and it is one string.
    """
    locale_dir = pathlib.Path(locale_dir)
    previous_dir = pathlib.Path(previous_dir)

    added = {}  # insertion-ordered; dict rather than set so output is stable
    for current in sorted(locale_dir.glob('*/LC_MESSAGES/django.po')):
        locale = current.parents[1].name
        previous = previous_dir / ('%s.po' % locale)
        before = set()
        if previous.exists():
            before = {entry.msgid for entry in polib.pofile(str(previous))}
        for entry in polib.pofile(str(current)):
            # polib yields neither the header nor obsolete entries
            if entry.msgid and entry.msgid not in before:
                added.setdefault(entry.msgid, None)
    return list(added)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: %s <locale-dir> <previous-dir>\n' % argv[0])
        return 2
    added = new_msgids(argv[1], argv[2])
    print(len(added))
    for msgid in added:
        print(msgid)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
