"""`poe test-gui` - the GUI suite, with the mode and browser chosen by name.

This is the verb that shows why §4 is worth doing, because every one of its
properties was awkward or impossible while the body lived in TOML.

**The two words can arrive in either order, or singly, or not at all.** poe
substitutes an unset argument out of a `cmd` entirely - measured, no empty token
and no dangling flag - so the task line
``python -m qatrack.qatrack_core.tasks test-gui ${mode} ${browser}`` passes
whichever were given, and `classify` works out which is which by vocabulary
rather than by position. `poe test-gui firefox headless` and
`poe test-gui headless firefox` are the same run.

**Omitting one overrides nothing.** `settings.py` reads both variables from the
environment and `local_test_settings.py` is imported afterwards, so leaving a
variable unset is what lets a developer's own choice through. A default on
either would silently take that away.

**Extras reach pytest.** `poe test-gui --mode headless -- -k test_x` arrives
here as trailing arguments and is appended to the pytest call. That stopped
working when the six browser-and-mode tasks became three with an argument, and
it works again here.

One asymmetry that is not this module's to fix: `settings.py` reads
``SELENIUM_BROWSER`` from the environment and `local_test_settings.py` is
imported after it, so a value pinned in that file beats what is set here. It is
what makes the no-argument case work, and it means a developer who has pinned
the browser there will find the argument ignored with nothing said. The fix
would be in `live.py`, which would have to prefer the environment.
"""

import os
import subprocess
import sys

MODES = {
    'headless': {'SELENIUM_HEADLESS': 'True'},
    'visible': {'SELENIUM_HEADLESS': 'False'},
    # Watching is visible plus a pause. SELENIUM_SLOW_MO is read straight from
    # the environment in live.py rather than exposed as a setting, so it cannot
    # be left switched on in a settings file - and cannot be overridden from
    # one either.
    'watch': {'SELENIUM_HEADLESS': 'False', 'SELENIUM_SLOW_MO': '0.4'},
}

BROWSERS = ('firefox', 'chromium', 'edge')


def classify(words):
    """Sort the given words into (mode, browser), in any order.

    Raises SystemExit with a message naming both vocabularies, which is the
    thing argparse cannot do for two positionals: it can only complain that a
    browser is not a valid mode, which is true and unhelpful when the real
    fault is the order.
    """
    mode = browser = None
    for word in words:
        if word in MODES and mode is None:
            mode = word
        elif word in BROWSERS and browser is None:
            browser = word
        else:
            raise SystemExit(
                "test-gui: don't know %r.\n"
                '  modes:    %s\n'
                '  browsers: %s' % (word, ', '.join(MODES), ', '.join(BROWSERS))
            )
    return mode, browser


def run(args, extra):
    mode, browser = classify(args.words)
    if browser:
        os.environ['SELENIUM_BROWSER'] = browser
    if mode:
        os.environ.update(MODES[mode])

    shown = mode or 'mode from your settings'
    if mode and os.environ.get('SELENIUM_SLOW_MO'):
        shown += ', slowed to %ss between actions' % os.environ['SELENIUM_SLOW_MO']
    print('GUI tests: %s, %s' % (browser or 'browser from your settings', shown))
    sys.stdout.flush()

    return subprocess.run(
        [sys.executable, '-m', 'pytest', '-m', 'selenium', *extra]
    ).returncode


def add_parser(verbs):
    parser = verbs.add_parser('test-gui', help='the GUI suite')
    parser.add_argument('words', nargs='*', help='a mode and/or a browser, in either order')
    parser.set_defaults(run=run)
