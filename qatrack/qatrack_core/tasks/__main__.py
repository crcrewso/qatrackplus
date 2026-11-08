"""Dispatch `python -m qatrack.qatrack_core.tasks <verb> [...]`.

One entry point rather than one module per verb, so a poe task is a single
predictable line and `--help` works for every verb without poe.

Unrecognised trailing arguments are handed to the verb rather than refused,
because that is the whole point of being a `cmd`: `poe test-gui --mode headless
-- -k test_x` has to reach pytest.
"""

import argparse
import sys

from . import ci_reminder, cover, gui


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m qatrack.qatrack_core.tasks')
    verbs = parser.add_subparsers(dest='verb', required=True)

    for module in (gui, cover, ci_reminder):
        module.add_parser(verbs)

    known, extra = parser.parse_known_args(argv)
    return known.run(known, extra)


if __name__ == '__main__':
    sys.exit(main())
