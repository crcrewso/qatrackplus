"""`poe cover` - the suite with a coverage report.

Here to show the thing §3 could not do. Merging `cover-mo` into `cover` as
``--skip-covered`` needs a boolean argument, and a boolean substituted into a
poe `cmd` arrives as the word ``True`` rather than as the flag - measured on poe
0.49.0. So `cover`, `cover-qatrack` and `cover-module` could become one task
with an optional path, and `cover-mo` had to keep its own name.

With the body here, the flag is an ordinary argparse boolean and the fourth
coverage task folds in too: 4 names become 1 rather than 2. The same argument
applies to `lint --fix` and `test-engine --docker`, which were the other rows
§3 left on the table.
"""

import subprocess
import sys


def run(args, extra):
    report = 'term-missing:skip-covered' if args.skip_covered else 'term-missing'
    argv = [
        sys.executable, '-m', 'pytest', '--reuse-db',
        '--cov-report', report,
        '--cov', './%s' % (args.path or ''),
    ]
    if args.path:
        argv.append(args.path)
    return subprocess.run(argv + list(extra)).returncode


def add_parser(verbs):
    parser = verbs.add_parser('cover', help='the suite with a coverage report')
    parser.add_argument('path', nargs='?', help='qatrack, qatrack/qa, or any path; omit for everything')
    parser.add_argument(
        '--skip-covered', action='store_true',
        help='leave fully covered files out of the report',
    )
    parser.set_defaults(run=run)
