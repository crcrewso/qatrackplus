import re

from django.test import TestCase
from django.urls import reverse

from qatrack.accounts.tests.utils import create_user
from qatrack.qa import models
from qatrack.qa.tests import utils


class TestTestChangeFormUnitAssignments(TestCase):
    """The machines table in the Test admin change page's Used In card (R13; was the
    "Assigned to the following Units" list)."""

    def setUp(self):
        create_user(is_superuser=True, uname='user', pwd='pwd')
        self.client.login(username='user', password='pwd')

    def _get(self, test):
        resp = self.client.get(reverse('admin:qa_test_change', args=(test.pk,)))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _assignment_line(self, html, uti):
        """The machine's row: reference and tolerance cells, then the edit link."""
        start = html.index('<tr data-uti="%s">' % uti.pk)
        row = html[start:html.index('</tr>', start)]
        url = reverse('admin:qa_unittestinfo_change', args=(uti.pk,))
        self.assertIn('href="%s"' % url, row)
        return row

    def _cells(self, row):
        """(reference, tolerance) text from a machine row."""
        ref, tol = re.findall(r'<td class="tst-reftol[^"]*">(.*?)</td>', row, re.S)
        return ref.strip(), tol.strip()

    def test_missing_reference_and_tolerance_show_not_set(self):
        test = utils.create_test(name='no_ref_tol')
        uti = utils.create_unit_test_info(test=test)
        line = self._assignment_line(self._get(test), uti)
        self.assertEqual(self._cells(line), ('Not set', 'Not set'))
        self.assertIn('tst-not-set', line)
        self.assertNotIn('None', line)

    def test_numerical_reference_and_readable_tolerance(self):
        test = utils.create_test(name='numeric')
        ref = utils.create_reference(value=0)
        tol = utils.create_tolerance()
        uti = utils.create_unit_test_info(test=test, ref=ref, tol=tol)
        line = self._assignment_line(self._get(test), uti)
        ref_cell, tol_cell = self._cells(line)
        self.assertEqual(ref_cell, '0')
        self.assertNotIn('Not set', line)
        self.assertEqual(tol_cell, tol.plain_display())

    def test_boolean_reference_shows_yes_no(self):
        test = utils.create_test(name='bool', test_type=models.BOOLEAN)
        # Older admin versions saved Yes/No references with the numerical type.
        ref_yes = utils.create_reference(name='yes', ref_type=models.NUMERICAL, value=1)
        uti_yes = utils.create_unit_test_info(test=test, ref=ref_yes)
        ref_no = utils.create_reference(name='no', ref_type=models.BOOLEAN, value=0)
        uti_no = utils.create_unit_test_info(test=test, ref=ref_no)
        html = self._get(test)
        self.assertEqual(self._cells(self._assignment_line(html, uti_yes))[0], 'Yes')
        self.assertEqual(self._cells(self._assignment_line(html, uti_no))[0], 'No')
