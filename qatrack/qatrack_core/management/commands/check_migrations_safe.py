"""Produce the evidence the migration policy asks for, as a table for a pull request.

A command rather than a system check: it renders SQL on every configured
database, which needs connections and seconds, and its output is something a
developer pastes into a pull request body for a maintainer to read. The quick
yes-or-no gate - "is a migration missing?" - stays ``makemigrations --check``,
which ``poe check-migrations`` wraps.
"""

import datetime
import json
import os
import shutil
import subprocess

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from qatrack.qatrack_core import migration_safety as ms

HEADER = (
    'Evidence for the migration policy, not a verdict. The developer produces this; '
    'the maintainers judge it. OK means the evidence supports a patch release; REVIEW '
    'means a human or an engine is still owed; FAIL names the clause.'
)

CLAUSES = {
    ms.EFFECT: '1 metadata/additive/restores',
    ms.STRUCTURE: '2 no remove/rename/retype',
    ms.DATA: '3 no data-writing code',
    ms.REVERSIBLE: '4 reversible',
    ms.ENGINES: '5 engines',
}


class Command(BaseCommand):
    help = (
        'Report what the migrations a branch adds (and any unwritten model change) would do on every '
        'configured database, against the five clauses of the patch-release migration policy'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--base',
            metavar='REF',
            help='Git ref the branch is compared against to find added migrations '
            '(default: the first of upstream/develop, origin/develop, develop that exists).',
        )
        parser.add_argument(
            '--migration',
            action='append',
            default=[],
            metavar='APP.NAME',
            help='Examine this migration instead of the added ones; repeatable. '
            'NAME may be a unique prefix, e.g. qa.0061.',
        )
        parser.add_argument(
            '--no-unwritten',
            action='store_true',
            help='Do not examine model changes that makemigrations would still write.',
        )
        parser.add_argument(
            '--database',
            action='append',
            default=[],
            metavar='ALIAS',
            help='Render on this database alias; repeatable (default: every configured alias).',
        )
        parser.add_argument(
            '--reverse-on',
            metavar='ALIAS',
            help='Also reverse and re-apply each examined migration ON THIS DATABASE. Destructive for that '
            'database if a reverse fails; point it at a disposable one. A file-backed SQLite default is '
            'copied and the copy used, without this flag.',
        )
        parser.add_argument('--no-reverse', action='store_true', help='Skip the reverse-and-re-apply step entirely.')
        parser.add_argument(
            '--format',
            choices=['text', 'markdown', 'json'],
            default='text',
            help='text for a terminal, markdown to paste into a pull request, json for tooling.',
        )

    def handle(self, *args, **options):
        aliases = options['database'] or sorted(connections.databases)
        for alias in aliases:
            if alias not in connections.databases:
                raise CommandError(
                    'no database alias %r; configured: %s' % (alias, ', '.join(sorted(connections.databases)))
                )
        reference = aliases[0]
        loader = ms.loader_for(reference)

        targets = []  # (app_label, name, operations, from_state, source)
        if options['migration']:
            for spec in options['migration']:
                app_label, _, prefix = spec.partition('.')
                if not prefix:
                    raise CommandError('--migration takes APP.NAME, got %r' % spec)
                try:
                    migration = loader.get_migration_by_prefix(app_label, prefix)
                except KeyError:
                    raise CommandError('no migration %s in app %r' % (prefix, app_label))
                targets.append(self._target(loader, migration.app_label, migration.name, 'named'))
            base_ref = None
        else:
            base_ref = ms.resolve_base(options['base'])
            if base_ref is None:
                self.stderr.write(
                    'No base ref found (tried %s); only unwritten changes are examined.'
                    % (options['base'] or 'upstream/develop, origin/develop, develop')
                )
            else:
                for app_label, name in ms.added_migrations(base_ref):
                    if (app_label, name) in loader.graph.nodes:
                        targets.append(self._target(loader, app_label, name, 'added'))
                    else:
                        self.stderr.write(
                            '%s.%s was added but is not in the migration graph; skipped.' % (app_label, name)
                        )

        if not options['no_unwritten']:
            for app_label, name, operations in ms.unwritten_changes(loader):
                targets.append((app_label, name, operations, loader.project_state(), 'unwritten'))

        reports = [ms.examine(a, n, o, s, aliases, src) for a, n, o, s, src in targets]

        if not options['no_reverse']:
            for report in reports:
                if report.source == 'unwritten':
                    report.reverse['-'] = 'not written yet; nothing to reverse'
                    continue
                self._reverse(report, options['reverse_on'], reference)

        context = {
            'generated': datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%MZ'),
            'head': _git_head(),
            'base': base_ref,
            'engines': {alias: _engine_name(alias) for alias in aliases},
        }
        if options['format'] == 'json':
            self.stdout.write(json.dumps(_as_json(reports, context), indent=2, sort_keys=True))
        elif options['format'] == 'markdown':
            self.stdout.write(_markdown(reports, context))
        else:
            self.stdout.write(_text(reports, context))

        verdicts = {r.verdict for r in reports}
        if 'FAIL' in verdicts:
            raise SystemExit(1)
        if 'REVIEW' in verdicts:
            raise SystemExit(2)

    def _target(self, loader, app_label, name, source):
        migration = loader.get_migration(app_label, name)
        from_state = loader.project_state((app_label, name), at_end=False)
        return (app_label, name, list(migration.operations), from_state, source)

    def _reverse(self, report, reverse_on, reference):
        if reverse_on:
            report.reverse[reverse_on] = ms.reverse_and_reapply(report.app_label, report.name, reverse_on, call_command)
            return
        source_file = ms.sqlite_file_of(reference)
        if source_file is None:
            report.reverse[reference] = (
                'not run: no file-backed SQLite to copy; use --reverse-on ALIAS for a disposable database'
            )
            return
        copy = source_file.with_name('%s.check_migrations_safe.%d.sqlite3' % (source_file.name, os.getpid()))
        alias = '_check_migrations_safe_copy'
        shutil.copyfile(source_file, copy)
        connections.databases[alias] = {**connections.databases[reference], 'NAME': str(copy)}
        try:
            report.reverse['%s (copy)' % reference] = ms.reverse_and_reapply(
                report.app_label, report.name, alias, call_command
            )
        finally:
            try:
                connections[alias].close()
            except Exception:
                pass
            connections.databases.pop(alias, None)
            copy.unlink(missing_ok=True)


def _git_head():
    done = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ms.REPO_ROOT, capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else 'unknown'


def _engine_name(alias):
    return connections.databases[alias].get('ENGINE', '?').rsplit('.', 1)[-1]


def _engine_cell(report, alias):
    """One alias summarised across the migration's operations: no-op, DDL counts, python, or not reached."""
    errors = [f.errors[alias] for f in report.findings if alias in f.errors]
    if errors:
        return 'not reached: %s' % errors[0]
    statements = 0
    noop = 0
    python = 0
    for f in report.findings:
        sql = f.rendered.get(alias)
        if sql is None:
            python += 1
        elif sql:
            statements += len(sql)
        else:
            noop += 1
    bits = []
    if statements:
        bits.append('%d DDL statement%s' % (statements, '' if statements == 1 else 's'))
    if noop:
        bits.append('%d no-op' % noop)
    if python:
        bits.append('%d python' % python)
    return ', '.join(bits) or 'nothing rendered'


def _row(report, aliases):
    fails = report.clause_fails()

    def clause(n):
        if n in fails:
            return 'FAIL: ' + '; '.join(fails[n][:2]) + (' (+%d)' % (len(fails[n]) - 2) if len(fails[n]) > 2 else '')
        if n == ms.DATA:
            reading = report.needs_reading()
            return ('read: ' + '; '.join(f.describe for f in reading)) if reading else 'none'
        return 'ok'

    engines = '; '.join('%s: %s' % (alias, _engine_cell(report, alias)) for alias in aliases)
    reverse = '; '.join('%s: %s' % (k, v) for k, v in report.reverse.items()) or 'not run'
    return [
        report.label,
        '%d op%s (%s)' % (len(report.findings), '' if len(report.findings) == 1 else 's', report.source),
        clause(ms.EFFECT),
        clause(ms.STRUCTURE),
        clause(ms.DATA),
        clause(ms.REVERSIBLE),
        engines,
        reverse,
        report.verdict,
    ]


COLUMNS = [
    'Migration',
    'Operations',
    CLAUSES[1],
    CLAUSES[2],
    CLAUSES[3],
    CLAUSES[4],
    CLAUSES[5],
    'Reverse and re-apply',
    'Verdict',
]


def _markdown(reports, context):
    lines = [
        '**check_migrations_safe** at `%s`%s, %s. %s'
        % (
            context['head'],
            (' against `%s`' % context['base']) if context['base'] else '',
            context['generated'],
            HEADER,
        ),
        '',
        'Engines: ' + ', '.join('`%s` (%s)' % (a, e) for a, e in context['engines'].items()),
        '',
    ]
    if not reports:
        lines.append('No added migrations and no unwritten model changes.')
        return '\n'.join(lines) + '\n'
    lines.append('| ' + ' | '.join(COLUMNS) + ' |')
    lines.append('|' + '---|' * len(COLUMNS))
    for report in reports:
        lines.append('| ' + ' | '.join(_md(cell) for cell in _row(report, list(context['engines']))) + ' |')
    lines.append('')
    for report in reports:
        lines.append('<details><summary>%s: %d operations</summary>' % (report.label, len(report.findings)))
        lines.append('')
        for f in report.findings:
            notes = ('; '.join(f.notes)) if f.notes else ''
            engines = ', '.join(
                '%s %s' % (alias, 'python' if sql is None else ('no-op' if not sql else '%d stmt' % len(sql)))
                for alias, sql in f.rendered.items()
            )
            lines.append(
                '- %s: **%s**%s%s'
                % (
                    _md(f.describe),
                    f.category,
                    (' - ' + _md(notes)) if notes else '',
                    (' [%s]' % engines) if engines else '',
                )
            )
        lines.append('')
        lines.append('</details>')
        lines.append('')
    return '\n'.join(lines)


def _md(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def _text(reports, context):
    out = [
        'check_migrations_safe at %s%s, %s'
        % (context['head'], (' against %s' % context['base']) if context['base'] else '', context['generated'])
    ]
    out.append(HEADER)
    out.append('Engines: ' + ', '.join('%s (%s)' % (a, e) for a, e in context['engines'].items()))
    out.append('')
    if not reports:
        out.append('No added migrations and no unwritten model changes.')
        return '\n'.join(out) + '\n'
    for report in reports:
        row = _row(report, list(context['engines']))
        out.append('%s  [%s]  %s' % (row[0], row[-1], row[1]))
        for title, cell in zip(COLUMNS[2:-1], row[2:-1]):
            out.append('    %-28s %s' % (title, cell))
        for f in report.findings:
            engines = ', '.join(
                '%s %s' % (alias, 'python' if sql is None else ('no-op' if not sql else '%d stmt' % len(sql)))
                for alias, sql in f.rendered.items()
            )
            out.append(
                '      - %s: %s%s%s'
                % (
                    f.describe,
                    f.category,
                    (' - ' + '; '.join(f.notes)) if f.notes else '',
                    (' [%s]' % engines) if engines else '',
                )
            )
        out.append('')
    return '\n'.join(out)


def _as_json(reports, context):
    return {
        'context': context,
        'header': HEADER,
        'migrations': [
            {
                'migration': r.label,
                'source': r.source,
                'verdict': r.verdict,
                'clause_fails': {CLAUSES[k]: v for k, v in r.clause_fails().items()},
                'needs_reading': [f.describe for f in r.needs_reading()],
                'engines_not_reached': r.engines_not_reached(),
                'reverse': r.reverse,
                'operations': [
                    {
                        'describe': f.describe,
                        'category': f.category,
                        'reversible': f.reversible,
                        'notes': f.notes,
                        'rendered': {a: (None if s is None else len(s)) for a, s in f.rendered.items()},
                    }
                    for f in r.findings
                ],
            }
            for r in reports
        ],
    }
