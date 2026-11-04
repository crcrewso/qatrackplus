import csv
import io
import json
import pathlib

from django.core.management.base import BaseCommand, CommandError, OutputWrapper
from django.core.management.color import no_style
from django.db.models import Q

from qatrack.qa import calculation_check as cc
from qatrack.qa import models
from qatrack.units.models import Unit

TYPES = {
    'composite': models.COMPOSITE,
    'scomposite': models.STRING_COMPOSITE,
    'upload': models.UPLOAD,
    # any other test whose procedure sets a default value
    'default': None,
}


class Command(BaseCommand):
    """
    Check that tests' calculation procedures still run, and still give the
    results that were saved. See qatrack/qa/calculation_check.py.

    Exits with status 1 if any test is broken (or, with --strict, if any
    result changed or a warning was found), so it can be used in upgrade
    scripts.
    """

    help = (
        'Check that the calculation procedures of composite, string composite and file upload tests '
        '(and of any other test whose procedure sets a default value) still run, and still give the '
        'results that were saved. Run it after upgrading QATrack+ or the Python libraries it uses '
        '(NumPy in particular). Nothing is saved.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='append',
            dest='tests',
            metavar='TEST',
            help='Only check this test, given by ID, macro name or name. May be repeated.',
        )
        parser.add_argument(
            '--test-list',
            action='append',
            dest='test_lists',
            type=int,
            metavar='ID',
            help='Only check tests in the test list with this ID, including its sublists. May be repeated.',
        )
        parser.add_argument(
            '--type',
            action='append',
            dest='types',
            choices=list(TYPES),
            help=(
                'Only check tests of this type. "default" means any other test whose procedure '
                'sets a default value. May be repeated.'
            ),
        )
        parser.add_argument(
            '--unit',
            action='append',
            dest='units',
            type=int,
            metavar='NUMBER',
            help='Only recalculate results saved for the unit with this number. May be repeated.',
        )
        parser.add_argument(
            '--scan-only',
            action='store_true',
            help=(
                "Only scan the procedures' source code, without recalculating anything. Fast, needs "
                'no saved results, and reports what NumPy 2 removed even before upgrading.'
            ),
        )
        parser.add_argument(
            '--format',
            choices=['text', 'csv', 'json'],
            default='text',
            help='Output format (default: %(default)s).',
        )
        parser.add_argument(
            '--output',
            metavar='FILE',
            help=(
                'Save the report to this file (UTF-8) instead of printing it, to work from while '
                'fixing the tests in the admin. Only a summary is printed.'
            ),
        )
        parser.add_argument(
            '--rtol',
            type=float,
            default=cc.DEFAULT_RTOL,
            help='Relative tolerance when comparing recalculated numbers with saved ones (default: %(default)s).',
        )
        parser.add_argument(
            '--atol',
            type=float,
            default=cc.DEFAULT_ATOL,
            help='Absolute tolerance when comparing recalculated numbers with saved ones (default: %(default)s).',
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Also exit with status 1 when a result changed or a warning was found, not only when a test is broken.',
        )

    def handle(self, *args, **options):
        tests = self.select_tests(options)
        units = self.select_units(options)

        show_progress = options['format'] == 'text' and options['verbosity'] > 0 and self.stderr.isatty()
        checks = cc.check_tests(
            tests,
            recalculate=not options['scan_only'],
            units=units,
            rtol=options['rtol'],
            atol=options['atol'],
            progress=self.show_progress if show_progress else None,
        )
        if show_progress:
            self.stderr.write('\r%s\r' % (' ' * 60), ending='')

        report = io.StringIO() if options['output'] else None
        if report is not None:
            # a saved report is read later, in an editor or a spreadsheet:
            # no terminal colour codes, and UTF-8 whatever the console uses
            self.style = no_style()
            self.out = OutputWrapper(report)
        else:
            self.out = self.stdout

        writer = {'text': self.write_text, 'csv': self.write_csv, 'json': self.write_json}[options['format']]
        writer(checks, options)

        if report is not None:
            path = pathlib.Path(options['output'])
            try:
                path.write_text(report.getvalue(), encoding='utf-8')
            except OSError as e:
                raise CommandError('Could not write the report to %s: %s' % (path, e))
            self.stdout.write('Report written to %s' % path)
            self.stdout.write(self.summary_line(checks))

        failing = {cc.ERROR}
        if options['strict']:
            failing |= {cc.CHANGED, cc.WARNING}
        if any(check.status in failing for check in checks):
            raise SystemExit(1)

    def select_tests(self, options):
        tests = cc.tests_with_procedures()

        if options['tests']:
            query = Q()
            for given in options['tests']:
                match = Q(slug=given) | Q(name=given)
                if given.isdigit():
                    match |= Q(pk=int(given))
                if not tests.filter(match).exists():
                    raise CommandError(
                        "No test with a calculation procedure has the ID, macro name or name '%s'." % given
                    )
                query |= match
            tests = tests.filter(query)

        if options['test_lists']:
            ids = set()
            for pk in options['test_lists']:
                try:
                    test_list = models.TestList.objects.get(pk=pk)
                except models.TestList.DoesNotExist:
                    raise CommandError('There is no test list with ID %s.' % pk)
                ids.update(test_list.all_tests().values_list('pk', flat=True))
            tests = tests.filter(pk__in=ids)

        if options['types']:
            query = Q()
            for name in options['types']:
                if TYPES[name] is None:
                    query |= ~Q(type__in=models.CALCULATED_TYPES)
                else:
                    query |= Q(type=TYPES[name])
            tests = tests.filter(query)

        return tests

    def select_units(self, options):
        if not options['units']:
            return None
        units = list(Unit.objects.filter(number__in=options['units']))
        missing = set(options['units']) - {u.number for u in units}
        if missing:
            raise CommandError('There is no unit with number %s.' % ', '.join(str(n) for n in sorted(missing)))
        return units

    def show_progress(self, done, total, job):
        self.stderr.write('\rRecalculating %d of %d...' % (done + 1, total), ending='')
        self.stderr.flush()

    def write_text(self, checks, options):
        verbosity = options['verbosity']
        versions = ', '.join('%s %s' % item for item in cc.library_versions().items())

        if verbosity > 0:
            recalculated = sum(1 for c in checks for r in c.recalculations if r.status != cc.NOT_RUN)
            self.out.write('Checked %d test(s) with calculation procedures using %s.' % (len(checks), versions))
            if not options['scan_only']:
                self.out.write('Recalculated %d saved result(s) and sample file(s).' % recalculated)
            self.out.write('')

            for check in checks:
                if check.status != cc.OK or verbosity > 1:
                    self.write_check(check, verbosity)

        self.out.write(self.summary_line(checks))

    def summary_line(self, checks):
        counts = {status: 0 for status in cc.SEVERITY}
        for check in checks:
            counts[check.status] += 1
        summary = ', '.join('%s: %d' % (cc.STATUS_DISPLAY[s], counts[s]) for s in cc.SEVERITY if counts[s])
        return 'Summary: %s' % (summary or 'no tests with calculation procedures were found')

    def write_check(self, check, verbosity):
        test = check.test
        heading = '%s: %s (macro name %s, %s, ID %d)' % (
            cc.STATUS_DISPLAY[check.status],
            test.name,
            test.slug,
            cc.procedure_kind(test),
            test.pk,
        )
        self.out.write(self.styled(check.status, heading))

        for finding in check.findings:
            line = 'Line %s: ' % finding.line if finding.line else ''
            self.out.write(self.indent(line + finding.message, 4))

        for recalc in check.recalculations:
            if recalc.severity == cc.OK and verbosity < 2:
                continue
            text = '%s: %s' % (recalc.source, cc.STATUS_DISPLAY[recalc.severity])
            if recalc.message:
                text = '%s - %s' % (text, recalc.message)
            self.out.write(self.indent(text, 4))
            if recalc.detail and verbosity > 1:
                self.out.write(self.indent(recalc.detail, 8))
            for warning in recalc.warnings:
                self.out.write(self.indent(warning, 8))
            # values are worth showing when they differ, or when nothing was saved
            # to compare with (sample files, default values); identical ones are noise
            show_values = recalc.status == cc.CHANGED or verbosity > 1
            if recalc.saved and show_values:
                self.out.write(self.indent('saved:        %s' % recalc.saved, 8))
            if recalc.recalculated and (show_values or not recalc.saved):
                self.out.write(self.indent('recalculated: %s' % recalc.recalculated, 8))

        if check.recalculation_requested and not check.recalculations:
            self.out.write(self.indent('There are no saved results to recalculate it from.', 4))
        self.out.write('')

    def styled(self, status, text):
        style = {
            cc.ERROR: self.style.ERROR,
            cc.CHANGED: self.style.WARNING,
            cc.WARNING: self.style.WARNING,
            cc.OK: self.style.SUCCESS,
        }.get(status)
        return style(text) if style else text

    @staticmethod
    def indent(text, spaces):
        pad = ' ' * spaces
        return '\n'.join(pad + line for line in str(text).rstrip().splitlines())

    def write_csv(self, checks, options):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                'test_id',
                'test_name',
                'macro_name',
                'type',
                'test_status',
                'check',
                'check_status',
                'source',
                'line',
                'message',
                'saved',
                'recalculated',
                'detail',
            ]
        )
        for check in checks:
            test = check.test
            base = [test.pk, test.name, test.slug, test.type, check.status]
            rows = [['scan', f.status, '', f.line or '', f.message, '', '', ''] for f in check.findings]
            for r in check.recalculations:
                rows.append(['recalculation', r.status, r.source, '', r.message, r.saved, r.recalculated, r.detail])
                rows.extend(['runtime warning', cc.WARNING, r.source, '', w, '', '', ''] for w in r.warnings)
            for row in rows or [[''] * 8]:
                writer.writerow(base + row)
        self.out.write(out.getvalue(), ending='')

    def write_json(self, checks, options):
        data = {
            'versions': cc.library_versions(),
            'tests': [check.as_dict() for check in checks],
        }
        self.out.write(json.dumps(data, indent=2))
