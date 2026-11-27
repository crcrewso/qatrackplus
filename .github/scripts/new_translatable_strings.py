"""Which translatable strings a change adds, counted once each.

Used by the Translation Impact CI step. Compares the catalogues regenerated on
a change with those regenerated on its base, and reports the messages that are
new.

Why this is not a `grep` over the diff, which is what it replaced: gettext
writes a long message as `msgid ""` followed by quoted continuation lines, so
`^\\+msgid "` matches only short ones, and the bare `msgid ""` has to be
filtered out because it is also the header's. Every long string - which is to
say every real validation message - was therefore missing from the count and
from the report. Comparing catalogues as catalogues has no such blind spot.

Usage:

    new_translatable_strings.py <locale-dir> <previous-dir>

`previous-dir` holds the base's catalogues as `<locale>.po`. Prints the
count on the first line and one message per line after it, with its
context in brackets when it has one.
"""

import pathlib
import sys

import polib


def new_msgids(locale_dir, previous_dir):
    """Messages present in the regenerated catalogues and not in the previous ones.

    Keyed on (msgctxt, msgid), as gettext keys them: pgettext gives one text a
    translation per context. De-duplicated across locales, since
    `makemessages --all` adds the same string to every catalogue.
    """
    locale_dir = pathlib.Path(locale_dir)
    previous_dir = pathlib.Path(previous_dir)

    added = {}  # insertion-ordered; dict rather than set so output is stable
    for current in sorted(locale_dir.glob('*/LC_MESSAGES/django.po')):
        locale = current.parents[1].name
        previous = previous_dir / ('%s.po' % locale)
        before = set()
        if previous.exists():
            before = {(entry.msgctxt, entry.msgid) for entry in polib.pofile(str(previous))}
        for entry in polib.pofile(str(current)):
            key = (entry.msgctxt, entry.msgid)
            # polib yields neither the header nor obsolete entries
            if entry.msgid and key not in before:
                added.setdefault(key, None)
    return [msgid if context is None else '%s (context: %s)' % (msgid, context) for context, msgid in added]


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
