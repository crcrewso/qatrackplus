"""What `poe ci` prints when it is green.

The smallest body in `poe_tasks/`, and the one whose noise mattered most: `ci`
is the pre-push command, so its six lines of `print()` calls were echoed to
everybody, after four clean `Poe =>` lines for the real checks.
"""

STILL_ONLY_CI = [
    'the suite on postgres / mysql / mssql   (poe test-engine <engine>)',
    'the suite on Windows                     (no local equivalent)',
    'the Selenium suite, firefox and chromium (poe test-gui)',
    'the Docker build-and-run check           (deploy/docker)',
]


def run(args, extra):
    print()
    print('Locally green. Still only run by CI:')
    for line in STILL_ONLY_CI:
        print('  - %s' % line)
    return 0


def add_parser(verbs):
    verbs.add_parser('ci-reminder', help='(internal) printed after a green `poe ci`').set_defaults(run=run)
