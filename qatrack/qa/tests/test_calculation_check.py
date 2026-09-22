import io
import json
import pathlib
import shutil
import tempfile

from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from qatrack.attachments.models import Attachment
from qatrack.qa import calculation_check as cc
from qatrack.qa import models
from qatrack.qa.tests import utils

# What a NumPy 2 removal is reported as depends on which NumPy is installed:
# a prediction under NumPy 1, a certainty under NumPy 2.
REMOVED = cc.ERROR if cc.NUMPY_MAJOR >= 2 else cc.WARNING


def scan(source):
    return [(f.status, f.line, f.message) for f in cc.scan_procedure(source)]


class TestScanProcedure(SimpleTestCase):
    def test_clean_procedure(self):
        assert scan('import numpy as np\nresult = np.mean([a, b])') == []

    def test_empty_procedure(self):
        assert scan('') == []
        assert scan(None) == []

    def test_syntax_error(self):
        [(status, line, message)] = scan('x = 1\nresult = (x +')
        assert status == cc.ERROR
        assert line == 2
        assert 'not valid Python' in message

    def test_numpy_from_calculation_context(self):
        """`numpy` is available without importing it"""
        [(status, line, message)] = scan('result = numpy.NaN')
        assert status == REMOVED
        assert line == 1
        assert '`numpy.NaN`' in message and '`np.nan`' in message

    def test_numpy_alias(self):
        [(status, line, message)] = scan('import numpy as np\n\nresult = np.product([a, b])')
        assert status == REMOVED
        assert line == 3
        assert '`np.product`' in message and '`np.prod`' in message

    def test_from_numpy_import(self):
        [(status, line, message)] = scan('from numpy import NaN\nresult = NaN')
        assert (status, line) == (REMOVED, 1)
        assert '`numpy.NaN`' in message

    def test_star_import(self):
        [(status, line, message)] = scan('from numpy import *\nresult = alltrue([a])')
        assert (status, line) == (REMOVED, 2)
        assert '`np.all`' in message

    def test_submodule_alias(self):
        [(status, line, message)] = scan('import numpy.linalg as la\nresult = la.linalg.norm([a])')
        assert (status, line) == (REMOVED, 2)
        assert '`la.linalg`' in message

    def test_removed_module_reported_once(self):
        """A problem that's the imported module itself is reported where it's imported, not on every use"""
        source = 'import numpy.lib.function_base as fb\nx = fb.interp(1, [0, 2], [0, 4])\nresult = fb.interp(x, [0, 2], [0, 4])'
        [(status, line, message)] = scan(source)
        assert (status, line) == (REMOVED, 1)
        assert '`numpy.lib.function_base`' in message

    def test_reassigned_alias_is_not_numpy(self):
        assert scan('import numpy as np\nnp = {"NaN": 1}\nresult = np.NaN') == []

    def test_numpy_core(self):
        [(status, line, message)] = scan('from numpy.core import multiarray\nresult = 1')
        assert (status, line) == (cc.WARNING, 1)
        assert '`numpy._core`' in message

    def test_not_in_installed_numpy(self):
        [(status, line, message)] = scan('result = numpy.definitely_not_a_numpy_function(a)')
        assert status == cc.ERROR
        assert cc.NUMPY_VERSION in message

    def test_array_copy_false(self):
        [(status, line, message)] = scan('import numpy as np\nresult = np.array([a], copy=False)')
        assert (status, line) == (cc.WARNING, 2)
        assert 'np.asarray' in message
        assert scan('import numpy as np\nresult = np.array([a], copy=True)') == []

    def test_lstsq_rcond(self):
        [(status, line, message)] = scan('result = numpy.linalg.lstsq(x, y)[0][0]')
        assert status == cc.WARNING
        assert 'rcond' in message
        assert scan('result = numpy.linalg.lstsq(x, y, rcond=None)[0][0]') == []
        assert scan('result = numpy.linalg.lstsq(x, y, None)[0][0]') == []

    def test_removed_array_methods(self):
        [(status, line, message)] = scan('result = values.ptp()')
        assert status == cc.WARNING
        assert '`values`' in message and 'np.ptp' in message
        assert scan('result = numpy.ptp(values)') == []

    def test_dtype_newbyteorder_still_exists(self):
        assert scan('result = values.dtype.newbyteorder(">")') == []

    def test_crlf_line_numbers(self):
        [(status, line, message)] = scan('x = 1\r\ny = 2\r\nresult = numpy.NaN')
        assert line == 3


class CalculationCheckTestCase(TestCase):
    """A unit performing a test list of two numbers and their total"""

    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        media_settings = override_settings(MEDIA_ROOT=media)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        self.user = utils.create_user()
        self.status = utils.create_status()
        self.unit = utils.create_unit()
        self.test_list = utils.create_test_list('Daily QA')
        self.a = self.make_test('a')
        self.b = self.make_test('b')
        self.total = self.make_test('total', models.COMPOSITE, 'result = a + b')
        self.utc = utils.create_unit_test_collection(unit=self.unit, test_collection=self.test_list)

    def make_test(self, slug, test_type=models.SIMPLE, procedure=None):
        test = utils.create_test(name=slug, test_type=test_type)
        test.calculation_procedure = procedure
        test.save()
        utils.create_test_list_membership(self.test_list, test, order=models.Test.objects.count())
        return test

    def perform(self, values, utc=None, work_completed=None):
        """Save a test list instance. `values` maps tests to a value, or to a dict of TestInstance fields."""
        utc = utc or self.utc
        tli = utils.create_test_list_instance(
            unit_test_collection=utc,
            work_completed=work_completed or timezone.now(),
            created_by=self.user,
        )
        for test, value in values.items():
            uti = models.UnitTestInfo.objects.get(unit=utc.unit, test=test)
            ti = utils.create_test_instance(
                tli,
                uti,
                value=None,
                created_by=self.user,
                work_completed=tli.work_completed,
                status=self.status,
            )
            for name, field_value in (value if isinstance(value, dict) else {'value': value}).items():
                setattr(ti, name, field_value)
            ti.save()
        return tli

    def set_procedure(self, test, procedure):
        test.calculation_procedure = procedure
        test.save()

    def check(self, test, **kwargs):
        [check] = cc.check_tests([test], **kwargs)
        return check

    def upload(self, content, name='data.json', **kwargs):
        return Attachment.objects.create(
            attachment=ContentFile(content, name),
            label=kwargs.pop('label', name),
            created_by=self.user,
            **kwargs,
        )


class TestRecalculation(CalculationCheckTestCase):
    def test_unchanged(self):
        self.perform({self.a: 1.5, self.b: 2, self.total: 3.5})
        check = self.check(self.total)
        assert check.status == cc.OK
        [recalc] = check.recalculations
        assert recalc.status == cc.OK
        assert (recalc.saved, recalc.recalculated) == ('3.5', '3.5')
        assert 'Daily QA' in recalc.source

    def test_changed(self):
        self.perform({self.a: 1.5, self.b: 2, self.total: 3.5})
        self.set_procedure(self.total, 'result = a * b')
        check = self.check(self.total)
        assert check.status == cc.CHANGED
        [recalc] = check.recalculations
        assert (recalc.saved, recalc.recalculated) == ('3.5', '3.0')
        assert 'relative difference' in recalc.message

    def test_within_tolerance(self):
        self.perform({self.a: 1.5, self.b: 2, self.total: 3.5 + 1e-13})
        assert self.check(self.total).status == cc.OK
        assert self.check(self.total, rtol=0, atol=0).status == cc.CHANGED

    def test_broken(self):
        self.perform({self.a: 1.5, self.b: 2, self.total: 3.5})
        self.set_procedure(self.total, 'x = 1\nresult = numpy.definitely_not_a_numpy_function(a)')
        check = self.check(self.total)
        assert check.status == cc.ERROR
        [recalc] = check.recalculations
        assert recalc.message.startswith('Line 2: AttributeError: ')
        assert 'definitely_not_a_numpy_function' in recalc.message
        assert 'Traceback' not in recalc.message and 'line 2' in recalc.detail

    def test_only_latest_result_per_unit(self):
        self.perform(
            {self.a: 1, self.b: 1, self.total: 999}, work_completed=timezone.now() - timezone.timedelta(days=1)
        )
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        assert [r.status for r in self.check(self.total).recalculations] == [cc.OK]

    def test_skipped_results_are_passed_over(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3}, work_completed=timezone.now() - timezone.timedelta(days=1))
        self.perform({self.a: None, self.b: None, self.total: {'skipped': True}})
        [recalc] = self.check(self.total).recalculations
        assert recalc.status == cc.OK
        assert recalc.saved == '3.0'

    def test_every_unit(self):
        unit2 = utils.create_unit()
        utc2 = utils.create_unit_test_collection(unit=unit2, test_collection=self.test_list)
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.perform({self.a: 1, self.b: 2, self.total: 4}, utc=utc2)
        check = self.check(self.total)
        assert sorted(r.status for r in check.recalculations) == [cc.CHANGED, cc.OK]
        assert check.status == cc.CHANGED

        # ...unless restricted to some of them
        assert [r.status for r in self.check(self.total, units=[self.unit]).recalculations] == [cc.OK]

    def test_no_saved_results(self):
        check = self.check(self.total)
        assert check.recalculations == []
        assert check.status == cc.NOT_RUN

    def test_scan_only(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(self.total, 'result = numpy.NaN')
        check = self.check(self.total, recalculate=False)
        assert check.recalculations == []
        assert check.status == REMOVED

    def test_input_missing(self):
        """A test added to the list after the result was saved has no value to recalculate with"""
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.make_test('c')
        self.set_procedure(self.total, 'result = a + b + c')
        [recalc] = self.check(self.total).recalculations
        assert recalc.status == cc.NOT_RUN
        assert recalc.message.endswith(': c')

    def test_whole_numbers_arrive_as_integers(self):
        """The browser posts 2.0 as 2, which shows when a procedure formats it"""
        label = self.make_test('label', models.STRING_COMPOSITE, 'result = "a=%s, b=%s" % (a, b)')
        self.perform({self.a: 2.0, self.b: 2.5, self.total: 4.5, label: {'string_value': 'a=2, b=2.5'}})
        assert self.check(label).status == cc.OK

    def test_string_composite_saved_as_json(self):
        """Non-string results are saved by the page as JSON text"""
        summary = self.make_test('summary', models.STRING_COMPOSITE, 'result = {"a": a, "values": [a, b]}')
        self.perform({self.a: 1.5, self.b: 2, self.total: 3.5, summary: {'string_value': '{"a":1.5,"values":[1.5,2]}'}})
        assert self.check(summary).status == cc.OK

        self.set_procedure(summary, 'result = {"a": a, "values": [b, a]}')
        assert self.check(summary).status == cc.CHANGED

    def test_string_composite_repr_change(self):
        """What a NumPy 2 upgrade does to str() of a list of NumPy scalars"""
        text = self.make_test('text', models.STRING_COMPOSITE, 'result = str([numpy.float64(a)])')
        self.perform({self.a: 1.5, self.b: 2, self.total: 3.5, text: {'string_value': '[1.5]'}})
        expected = cc.CHANGED if cc.NUMPY_MAJOR >= 2 else cc.OK
        assert self.check(text).status == expected

    def test_dates(self):
        day = self.make_test('day', models.DATE)
        when = self.make_test('when', models.DATETIME)
        gap = self.make_test('gap', models.COMPOSITE, 'result = (when.date() - day).days')
        now = timezone.now()
        self.perform(
            {
                self.a: 1,
                self.b: 2,
                self.total: 3,
                day: {'date_value': (now - timezone.timedelta(days=3)).date()},
                when: {'datetime_value': now},
                gap: 3,
            }
        )
        assert self.check(gap).status == cc.OK

    def test_meta(self):
        info = self.make_test(
            'info',
            models.STRING_COMPOSITE,
            'result = "%s %s %s" % (META["unit_number"], META["test_list_name"], META["work_completed"].year)',
        )
        tli = self.perform({self.a: 1, self.b: 2, self.total: 3})
        expected = '%s Daily QA %s' % (self.unit.number, tli.work_completed.year)
        models.TestInstance.objects.create(
            unit_test_info=models.UnitTestInfo.objects.get(unit=self.unit, test=info),
            test_list_instance=tli,
            string_value=expected,
            status=self.status,
            created_by=self.user,
            modified_by=self.user,
            work_started=tli.work_started,
            work_completed=tli.work_completed,
        )
        assert self.check(info).status == cc.OK

    def test_not_its_own_previous_result(self):
        """
        A result saved with work_started == work_completed (as through the
        API) would otherwise be found by UTILS.previous_test_instance as its
        own previous result.
        """
        change = self.make_test('change', models.COMPOSITE, 'result = a - UTILS.previous_test_instance("a").value')
        self.perform(
            {self.a: 1, self.b: 1, self.total: 2, change: 0}, work_completed=timezone.now() - timezone.timedelta(days=1)
        )
        tli = self.perform({self.a: 5, self.b: 1, self.total: 6, change: 4})
        models.TestListInstance.objects.filter(pk=tli.pk).update(work_started=tli.work_completed)
        assert self.check(change).status == cc.OK

    def test_nothing_is_saved(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(
            self.total,
            '\n'.join(
                [
                    'from qatrack.qa.models import Category',
                    'Category.objects.create(name="made by a procedure", slug="made-by-a-procedure")',
                    'UTILS.write_file("notes.txt", "some text")',
                    'result = a + b',
                ]
            ),
        )
        attachments = Attachment.objects.count()
        assert self.check(self.total).status == cc.OK
        assert not models.Category.objects.filter(slug='made-by-a-procedure').exists()
        assert Attachment.objects.count() == attachments

    def test_write_file_conversion_still_checked(self):
        """Objects are still converted to file contents, so a conversion that now fails is caught"""
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(
            self.total,
            '\n'.join(
                [
                    'class Unreadable:',
                    '    def read(self):',
                    '        raise ValueError("cannot be read")',
                    'UTILS.write_file("thing.bin", Unreadable())',
                    'result = a + b',
                ]
            ),
        )
        check = self.check(self.total)
        assert check.status == cc.ERROR
        assert 'cannot be read' in check.recalculations[0].message

    def test_default_value_procedure(self):
        self.set_procedure(self.b, 'b = a * 2')
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        check = self.check(self.b)
        assert check.status == cc.OK
        [recalc] = check.recalculations
        assert recalc.recalculated == '2'

        self.set_procedure(self.b, 'b = numpy.definitely_not_a_numpy_function(a)')
        assert self.check(self.b).status == cc.ERROR

    def test_removed_from_test_list(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        models.TestListMembership.objects.filter(test=self.total).delete()
        [recalc] = self.check(self.total).recalculations
        assert recalc.status == cc.NOT_RUN
        assert 'no longer part of the test list' in recalc.message

    def test_deprecation_warnings(self):
        """Libraries warn before removing things; a warning from the procedure's own code is reported"""
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(
            self.total,
            'import warnings\nwarnings.warn("going away soon", FutureWarning)\nresult = a + b',
        )
        check = self.check(self.total)
        assert check.status == cc.WARNING
        [recalc] = check.recalculations
        assert recalc.status == cc.OK
        assert recalc.warnings == ['Line 2: FutureWarning: going away soon']

    def test_deprecation_warning_pointing_past_the_procedure(self):
        """
        NumPy 1.26's np.product warning uses a stacklevel that lands on the
        line in perform.py that runs the procedure; it's still the procedure's.
        """
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(
            self.total,
            '\n'.join(
                [
                    'import warnings',
                    'def old_function():',
                    '    warnings.warn("renamed", DeprecationWarning, stacklevel=3)',
                    'old_function()',
                    'result = a + b',
                ]
            ),
        )
        [recalc] = self.check(self.total).recalculations
        assert recalc.warnings == ['Line 3: DeprecationWarning: renamed']

    def test_warnings_pointing_elsewhere_are_ignored(self):
        """e.g. inside a library: that library's business, not the procedure's"""
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(
            self.total,
            '\n'.join(
                [
                    'import warnings',
                    'def library_function():',
                    '    warnings.warn("internal", DeprecationWarning, stacklevel=4)',
                    'library_function()',
                    'result = a + b',
                ]
            ),
        )
        assert self.check(self.total).recalculations[0].warnings == []

    def test_test_list_crash(self):
        """A procedure that can't even be tokenized stops the whole test list"""
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        models.Test.objects.filter(pk=self.total.pk).update(calculation_procedure='result = """a + b')
        self.total.refresh_from_db()
        check = self.check(self.total)
        assert check.status == cc.ERROR
        assert any(f.status == cc.ERROR for f in check.findings)


class TestUploadRecalculation(CalculationCheckTestCase):
    def setUp(self):
        super().setUp()
        self.upload_test = self.make_test('analysis', models.UPLOAD, 'import json\nresult = json.load(FILE)')
        self.data = {'mean': 1.5, 'values': [1, 2]}

    def perform_upload(self, json_value=None):
        attachment = self.upload(json.dumps(self.data).encode())
        tli = self.perform(
            {
                self.a: 1,
                self.b: 2,
                self.total: 3,
                self.upload_test: {
                    'string_value': str(attachment.pk),
                    'json_value': json.dumps(self.data if json_value is None else json_value),
                },
            }
        )
        attachment.testinstance = tli.testinstance_set.get(unit_test_info__test=self.upload_test)
        attachment.save()
        return attachment

    def test_unchanged(self):
        self.perform_upload()
        check = self.check(self.upload_test)
        assert check.status == cc.OK
        assert json.loads(check.recalculations[0].recalculated) == self.data

    def test_changed(self):
        self.perform_upload(json_value={'mean': 1.4, 'values': [1, 2]})
        assert self.check(self.upload_test).status == cc.CHANGED

    def test_broken(self):
        self.perform_upload()
        self.set_procedure(self.upload_test, 'result = numpy.definitely_missing')
        assert self.check(self.upload_test).status == cc.ERROR

    def test_deprecation_warnings(self):
        self.perform_upload()
        self.set_procedure(
            self.upload_test,
            'import json, warnings\nwarnings.warn("old", DeprecationWarning)\nresult = json.load(FILE)',
        )
        [recalc] = self.check(self.upload_test).recalculations
        assert recalc.warnings == ['Line 2: DeprecationWarning: old']

    def test_file_missing(self):
        attachment = self.perform_upload()
        attachment.attachment.delete(save=False)
        check = self.check(self.upload_test)
        assert check.status == cc.NOT_RUN
        assert 'missing from storage' in check.recalculations[0].message

    def test_upload_results_used_by_composites(self):
        mean = self.make_test('mean', models.COMPOSITE, 'result = analysis["mean"] * 2')
        attachment = self.upload(json.dumps(self.data).encode())
        self.perform(
            {
                self.a: 1,
                self.b: 2,
                self.total: 3,
                self.upload_test: {'string_value': str(attachment.pk), 'json_value': json.dumps(self.data)},
                mean: 3,
            }
        )
        assert self.check(mean).status == cc.OK

    def test_sample_file(self):
        """A file attached to the test itself, for a test that's never been performed"""
        self.upload(json.dumps(self.data).encode(), label='check_calculations: example', test=self.upload_test)
        check = self.check(self.upload_test)
        assert check.status == cc.OK
        [recalc] = check.recalculations
        assert 'Sample file' in recalc.source
        assert json.loads(recalc.recalculated) == self.data

    def test_other_test_attachments_are_not_samples(self):
        self.upload(b'<html>how to perform this test</html>', name='procedure.html', test=self.upload_test)
        assert self.check(self.upload_test).recalculations == []

    def test_sample_file_broken(self):
        self.upload(b'not json', label='check_calculations', test=self.upload_test)
        assert self.check(self.upload_test).status == cc.ERROR

    def test_sample_file_test_not_assigned(self):
        test = utils.create_test('unassigned', test_type=models.UPLOAD)
        test.calculation_procedure = 'result = 1'
        test.save()
        self.upload(b'1', label='check_calculations', test=test)
        assert self.check(test).status == cc.NOT_RUN


class TestJob(SimpleTestCase):
    def test_round_trip(self):
        job = cc.Job('list', [1, 2], test_list_instance_id=3)
        assert cc.Job.from_dict(json.loads(json.dumps(job.as_dict()))) == job

    def test_invalid(self):
        for data in [
            {'kind': 'bogus', 'test_ids': [1], 'test_list_instance_id': 1},
            {'kind': 'list', 'test_ids': [], 'test_list_instance_id': 1},
            {'kind': 'list', 'test_ids': [1]},
            {'kind': 'sample', 'test_ids': [1]},
            {'kind': 'list', 'test_ids': ['x'], 'test_list_instance_id': 1},
        ]:
            with self.assertRaises(ValueError):
                cc.Job.from_dict(data)


class TestStatus(SimpleTestCase):
    def check(self, findings=(), recalculations=(), requested=True):
        return cc.TestCheck(
            None,
            [cc.Finding(s, '') for s in findings],
            [cc.Recalculation(s, '') for s in recalculations],
            requested,
        )

    def test_status(self):
        assert self.check(recalculations=[cc.OK]).status == cc.OK
        assert self.check().status == cc.NOT_RUN
        assert self.check(requested=False).status == cc.OK
        assert self.check(recalculations=[cc.NOT_RUN]).status == cc.NOT_RUN
        # recalculated on one unit is enough
        assert self.check(recalculations=[cc.NOT_RUN, cc.OK]).status == cc.OK
        assert self.check([cc.WARNING], [cc.OK]).status == cc.WARNING
        assert self.check([cc.WARNING], [cc.CHANGED]).status == cc.CHANGED
        assert self.check([cc.WARNING], [cc.ERROR, cc.CHANGED]).status == cc.ERROR


class TestCommand(CalculationCheckTestCase):
    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        try:
            call_command('check_calculations', *args, stdout=out, stderr=err)
            code = 0
        except SystemExit as e:
            code = e.code
        return code, out.getvalue()

    def test_all_ok(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        code, out = self.call()
        assert code == 0
        assert 'Summary: OK: 1' in out

    def test_broken(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(self.total, 'result = a + numpy.definitely_missing')
        code, out = self.call()
        assert code == 1
        assert 'Broken: total' in out
        assert 'definitely_missing' in out

    def test_changed(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(self.total, 'result = a * b')
        code, out = self.call()
        assert code == 0
        assert 'Changed: total' in out
        assert 'saved:        3.0' in out
        assert 'recalculated: 2' in out
        assert self.call('--strict')[0] == 1

    def test_scan_only(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(self.total, 'result = a * b')
        code, out = self.call('--scan-only')
        assert code == 0
        assert 'Summary: OK: 1' in out

    def test_filters(self):
        other = self.make_test('other', models.COMPOSITE, 'result = numpy.definitely_missing')
        assert self.call('--test', 'total')[0] == 0
        assert self.call('--test', str(other.pk))[0] == 1
        assert self.call('--type', 'scomposite')[1].startswith('Checked 0 test(s)')
        assert self.call('--test-list', str(self.test_list.pk))[0] == 1
        with self.assertRaises(CommandError):
            self.call('--test', 'no such test')
        with self.assertRaises(CommandError):
            self.call('--unit', '9999')

    def test_json(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        code, out = self.call('--format', 'json')
        data = json.loads(out)
        assert data['versions']['numpy'] == cc.NUMPY_VERSION
        [test] = data['tests']
        assert (test['macro_name'], test['status']) == ('total', cc.OK)
        assert test['recalculations'][0]['saved'] == '3.0'

    def test_csv(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        code, out = self.call('--format', 'csv')
        lines = out.splitlines()
        assert lines[0].startswith('test_id,test_name,macro_name')
        assert len(lines) == 2


class TestAdminPage(CalculationCheckTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('admin:qa_check_calculations')
        self.run_url = reverse('admin:qa_check_calculations_run')
        self.client.force_login(self.user)

    def remove_superuser(self):
        self.user.is_superuser = False
        self.user.save()

    def post_job(self, job):
        return self.client.post(self.run_url, json.dumps(job), content_type='application/json')

    def test_linked_from_test_list(self):
        response = self.client.get(reverse('admin:qa_test_changelist'))
        self.assertContains(response, self.url)

    def test_scan_shown(self):
        self.set_procedure(self.total, 'result = numpy.definitely_missing')
        response = self.client.get(self.url)
        self.assertContains(response, 'definitely_missing')
        self.assertContains(response, 'data-test-id="%d"' % self.total.pk)

    def test_jobs_planned(self):
        tli = self.perform({self.a: 1, self.b: 2, self.total: 3})
        response = self.client.get(self.url)
        assert response.context['page_data']['jobs'] == [cc.Job('list', [self.total.pk], tli.pk).as_dict()]

    def test_run(self):
        tli = self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(self.total, 'result = a * b')
        response = self.post_job(cc.Job('list', [self.total.pk], tli.pk).as_dict())
        [result] = response.json()['results']
        assert result['test_id'] == self.total.pk
        assert (result['status'], result['severity']) == (cc.CHANGED, cc.CHANGED)
        assert (result['saved'], result['recalculated']) == ('3.0', '2')

    def test_run_invalid_job(self):
        assert self.post_job({'kind': 'nonsense'}).status_code == 400
        response = self.client.post(self.run_url, 'not json', content_type='application/json')
        assert response.status_code == 400

    def test_run_missing_instance(self):
        [result] = self.post_job(cc.Job('list', [self.total.pk], 999999).as_dict()).json()['results']
        assert result['status'] == cc.ERROR

    def test_permission_required(self):
        self.remove_superuser()
        assert self.client.get(self.url).status_code == 403
        assert self.post_job(cc.Job('list', [self.total.pk], 1).as_dict()).status_code == 403

        self.user.user_permissions.add(Permission.objects.get(codename='change_test'))
        assert self.client.get(self.url).status_code == 200


class TestCommandOutputFile(CalculationCheckTestCase):
    def call(self, *args):
        out = io.StringIO()
        try:
            call_command('check_calculations', *args, stdout=out, stderr=io.StringIO())
        except SystemExit:
            pass
        return out.getvalue()

    def report(self, *args):
        path = pathlib.Path(tempfile.mkdtemp()) / 'report.txt'
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        printed = self.call('--output', str(path), *args)
        return path, printed

    def test_saves_report(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        self.set_procedure(self.total, 'result = a * b')
        path, printed = self.report()

        report = path.read_text(encoding='utf-8')
        assert 'Changed: total' in report
        assert 'saved:        3.0' in report
        # only a summary is printed, so the terminal doesn't repeat the report
        assert 'Changed: total' not in printed
        assert str(path) in printed
        assert 'Summary: Changed: 1' in printed

    def test_saves_csv(self):
        self.perform({self.a: 1, self.b: 2, self.total: 3})
        path, printed = self.report('--format', 'csv')
        assert path.read_text(encoding='utf-8').startswith('test_id,test_name')

    def test_no_colour_codes_in_report(self):
        self.set_procedure(self.total, 'result = numpy.definitely_missing')
        path, printed = self.report('--force-color')
        assert '\x1b[' not in path.read_text(encoding='utf-8')

    def test_unwritable_report(self):
        with self.assertRaises(CommandError):
            self.call('--output', str(pathlib.Path(tempfile.gettempdir()) / 'no-such-dir' / 'report.txt'))
