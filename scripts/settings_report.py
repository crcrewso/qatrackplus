#!/usr/bin/env python3
"""Summarise a local_settings.py so it can be pasted into a support request.

Run it on a deployment you need help upgrading::

    python scripts/settings_report.py

It prints a report and writes settings-report.md next to it. What you see is
exactly what gets written - there are no hidden fields.

Two deliberate constraints:

Nothing is executed.
    The file is parsed with ``ast``, never imported. Importing it would open
    your database, and possibly send mail or bind to LDAP, just to produce a
    report. Parsing also means a file too broken for Django to load still
    produces useful output, which is the case that matters most - a
    deployment whose settings will not load cannot run a management command.

Values are hidden unless a name is on an allowlist.
    Not a denylist. QATrack+ ships ~170 settings and deployments add their
    own, so "hide anything called PASSWORD" misses OPTIONS dictionaries,
    LDAP bind credentials and anything a site invented. Names not on the
    allowlist are reported as a type and a length. Paths and email addresses
    are hidden too: they carry account names and staff identities.

    Hidden values are fingerprinted with a short SHA-256. That is enough to
    tell whether two settings match, and whether one is still the example
    value published in this repository, without revealing it.

Stdlib only, no Django import, so it runs under any Python 3.8+.
"""

import argparse
import ast
import hashlib
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qatrack.qatrack_core.settings_registry import classify  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOCAL = os.path.join(HERE, 'qatrack', 'local_settings.py')
DEFAULT_SETTINGS = os.path.join(HERE, 'qatrack', 'settings.py')

# Values safe to print in full. Conservative on purpose: booleans, numbers,
# date formats, and identifiers that name code rather than describe a site.
# Anything that can carry a host name, path, address or credential is absent.
SAFE_TO_SHOW = {
    'DEBUG', 'USE_TZ', 'USE_I18N', 'USE_THOUSAND_SEPARATOR',
    'TIME_ZONE', 'LANGUAGE_CODE',
    'DATE_FORMAT', 'DATETIME_FORMAT', 'TIME_FORMAT',
    'DATE_INPUT_FORMATS', 'DATETIME_INPUT_FORMATS', 'TIME_INPUT_FORMATS',
    'MOMENT_DATE_FMT', 'MOMENT_DATETIME_FMT', 'MOMENT_TIME_FMT',
    'MOMENT_DATE_DATA_FMT', 'FLATPICKR_DATE_FMT', 'FLATPICKR_DATETIME_FMT',
    'SESSION_COOKIE_AGE', 'LANGUAGE_COOKIE_AGE', 'SESSION_COOKIE_SECURE',
    'CSRF_COOKIE_SECURE', 'SECURE_SSL_REDIRECT',
    'EMAIL_ENABLED', 'EMAIL_USE_TLS', 'EMAIL_USE_SSL', 'EMAIL_PORT',
    'EMAIL_FAIL_SILENTLY', 'EMAIL_TIMEOUT',
    'SELENIUM_BROWSER', 'SELENIUM_HEADLESS',
    'ACCOUNTS_SELF_REGISTER', 'ACCOUNTS_PASSWORD_RESET',
    'AUTH_LDAP_ALWAYS_UPDATE_USER', 'AD_LDAP_PORT',
    'USE_X_FORWARDED_HOST', 'PAPER_SIZE', 'VERSION', 'DEBUG_TOOLBAR',
    'CONSTANT_PRECISION', 'DEFAULT_NUMBER_FORMAT', 'DEFAULT_WARNING_MESSAGE',
    'TESTPACK_TIMEOUT', 'REVIEW_DIFF_MSG', 'ICON_SETTINGS',
    'CACHE_UNREVIEWED_COUNT', 'CACHE_TIMEOUT',
}

# Published in this repository and in deploy/*. Matching one is worth saying
# out loud; it is not a leak, because it is already public.
KNOWN_PLACEHOLDERS = [
    'YOUR_TIME_ZONE_GOES_HERE',
    'YOUR_EMAIL_ADDRESS_GOES_HERE',
    'your_password_here',
    'XX.XXX.XXX.XX',
    'CHANGE_ME',
]

# Deliberately absent: 'qatrackplus'. It is the documented database name and
# most deployments legitimately use it, so flagging it is noise, not a finding.


MAX_ITEMS = 6


def fingerprint(text):
    return hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()[:8]


def parse_assignments(path):
    """Return ({NAME: ast node}, [error strings]). Never executes the file."""
    try:
        with open(path, encoding='utf-8') as fh:
            source = fh.read()
    except OSError as exc:
        return {}, ["could not read %s: %s" % (path, exc.strerror)]

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return {}, [
            "%s has a syntax error on line %s: %s" % (path, exc.lineno, exc.msg)
        ]

    found = {}
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 2:
                found[target.id] = node.value
    return found, []


def literal(node):
    """Best-effort literal value, or None if it is an expression."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def describe(name, node):
    """Render a value: in full when the name is allowlisted, else a shape."""
    value = literal(node)
    computed = value is None and not isinstance(node, ast.Constant)

    if name in SAFE_TO_SHOW:
        if computed:
            return '<computed at import time>', None
        return repr(value), None

    if computed:
        return '<computed>', None

    if isinstance(value, bool) or value is None:
        return repr(value), None
    if isinstance(value, int | float):
        return '%s, hidden' % type(value).__name__, fingerprint(repr(value))
    if isinstance(value, str):
        return 'str, %d chars, hidden' % len(value), fingerprint(value)
    if isinstance(value, list | tuple | set):
        return '%s of %d, hidden' % (type(value).__name__, len(value)), fingerprint(repr(value))
    if isinstance(value, dict):
        return 'dict with keys %s, values hidden' % sorted(value)[:MAX_ITEMS], fingerprint(repr(value))
    return '%s, hidden' % type(value).__name__, fingerprint(repr(value))


def placeholders_in(node):
    """Which published placeholder values appear anywhere inside this value."""
    value = literal(node)
    if value is None:
        return []
    text = repr(value)
    return [p for p in KNOWN_PLACEHOLDERS if p in text]


def database_summary(node):
    """ENGINE and option keys only - NAME, USER, PASSWORD and HOST stay hidden."""
    value = literal(node)
    if not isinstance(value, dict):
        return []
    rows = []
    for alias, config in sorted(value.items()):
        if not isinstance(config, dict):
            continue
        engine = config.get('ENGINE', '<unset>')
        keys = sorted(k for k in config if k != 'ENGINE')
        rows.append((alias, engine, keys))
    return rows


def suspect_names(defined, known, cutoff=0.85):
    """Probable typos. High cutoff: catches TIMEZONE, ignores site helpers."""
    import difflib

    out = []
    for name in sorted(defined):
        if name in known or classify(name)[0]:
            continue
        close = difflib.get_close_matches(name, sorted(known), n=1, cutoff=cutoff)
        if close:
            out.append((name, close[0]))
    return out


def build_report(local_path, settings_path, show_all=False):
    lines = []
    w = lines.append

    local, errors = parse_assignments(local_path)
    defaults, _ = parse_assignments(settings_path)

    w('# QATrack+ settings report')
    w('')
    w('Generated by `scripts/settings_report.py`. Values are hidden unless the')
    w('setting name is on the allowlist in that script; hidden values are shown')
    w('as a type and an 8-character SHA-256 fingerprint. Nothing in this file was')
    w('executed to produce this report.')
    w('')
    w('## Environment')
    w('')
    w('| | |')
    w('|---|---|')
    w('| python | `%s` |' % platform.python_version())
    w('| platform | `%s` |' % platform.system())
    w('| local_settings.py | `%s` |' % ('found' if local else 'not found or unreadable'))
    w('| settings defined | %d |' % len(local))
    w('')

    if errors:
        w('## Could not read the file')
        w('')
        for err in errors:
            w('- %s' % err)
        w('')
        return '\n'.join(lines)

    # Two tables, because they call for different things. "Needs attention" is
    # a list of settings that are wrong or will stop working. "For review" is
    # context - the setting still works, but it does not mean quite what it
    # used to, which is the likeliest explanation for behaviour that changed
    # after an upgrade. Mixing the two makes a correctly-configured site look
    # broken.
    attention = []
    review = []

    for name in sorted(local):
        category, detail = classify(name)
        if category == 'removed':
            attention.append((
                name, 'removed in %s' % detail['version'],
                '%s %s' % (detail['why'], detail['action']),
            ))
        elif category == 'renamed':
            attention.append((
                name, 'renamed in %s' % detail['version'],
                'Now `%s`. %s' % (detail['new'], detail['note']),
            ))
        elif category == 'drifted':
            review.append((
                name, 'meaning changed in %s' % detail['version'],
                'Was: %s Now: %s' % (detail['was'], detail['now']),
            ))
        elif category == 'undeclared_but_read':
            review.append((
                name, 'still honoured',
                'Not declared in settings.py, but %s reads it. %s'
                % (detail['read_by'], detail['note']),
            ))

    for name in sorted(local):
        found = placeholders_in(local[name])
        if found:
            attention.append((
                name, 'unedited placeholder',
                'Still set to a value published in this repository: %s.'
                % ', '.join('`%s`' % p for p in found),
            ))

    for name, suggestion in suspect_names(set(local), set(defaults)):
        attention.append((
            name, 'possible typo',
            'No setting by this name exists. Did you mean `%s`?' % suggestion,
        ))

    # TIME_ZONE is the one that stops Django before any check can run, so it
    # is worth saying explicitly when it is missing rather than wrong.
    if 'TIME_ZONE' not in local:
        attention.append((
            'TIME_ZONE', 'not set',
            'settings.py ships a placeholder, so QATrack+ will refuse to start. '
            'Set it in local_settings.py.',
        ))

    def table(heading, rows, empty):
        w('## %s (%d)' % (heading, len(rows)))
        w('')
        if rows:
            w('| setting | what | detail |')
            w('|---|---|---|')
            for name, what, detail in rows:
                w('| `%s` | %s | %s |' % (name, what, detail.replace('|', '\\|')))
        else:
            w(empty)
        w('')

    table('Needs attention', attention, 'Nothing flagged.')
    table('For review', review, 'Nothing to review.')

    # --- databases -------------------------------------------------------
    if 'DATABASES' in local:
        w('## Databases')
        w('')
        w('Engine and which keys are set. Names, users, passwords and hosts are hidden.')
        w('')
        w('| alias | engine | keys set |')
        w('|---|---|---|')
        for alias, engine, keys in database_summary(local['DATABASES']):
            w('| `%s` | `%s` | %s |' % (alias, engine, ', '.join('`%s`' % k for k in keys) or '-'))
        w('')

    # --- what was changed ------------------------------------------------
    changed = []
    for name in sorted(local):
        if name == 'DATABASES':
            continue
        if not show_all and name in defaults:
            mine, theirs = literal(local[name]), literal(defaults[name])
            if mine is not None and mine == theirs:
                continue
        rendered, fp = describe(name, local[name])
        changed.append((name, rendered, fp))

    heading = 'All settings defined' if show_all else 'Settings that differ from the shipped defaults'
    w('## %s (%d)' % (heading, len(changed)))
    w('')
    if not show_all:
        w('Settings matching the default are omitted. Re-run with `--all` to include them.')
        w('')
    w('| setting | value | fingerprint |')
    w('|---|---|---|')
    for name, rendered, fp in changed:
        w('| `%s` | %s | %s |' % (name, rendered, '`%s`' % fp if fp else '-'))
    w('')

    w('## What this report does not contain')
    w('')
    w('- no passwords, secret keys, tokens or connection strings')
    w('- no host names, IP addresses, file system paths or email addresses')
    w('- no patient or clinical data of any kind')
    w('')
    w('Read it before sending. If anything above looks sensitive, delete the row')
    w('and say so - the report is still useful without it.')

    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('local_settings', nargs='?', default=DEFAULT_LOCAL,
                        help='path to local_settings.py (default: qatrack/local_settings.py)')
    parser.add_argument('--settings', default=DEFAULT_SETTINGS,
                        help='path to the shipped settings.py used for comparison')
    parser.add_argument('--all', action='store_true',
                        help='include settings that match the shipped default')
    parser.add_argument('-o', '--output', default='settings-report.md',
                        help="file to write (default: settings-report.md; '-' for stdout only)")
    args = parser.parse_args(argv)

    report = build_report(args.local_settings, args.settings, show_all=args.all)
    print(report)

    if args.output != '-':
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(report + '\n')
        print('\n[written to %s]' % args.output, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
