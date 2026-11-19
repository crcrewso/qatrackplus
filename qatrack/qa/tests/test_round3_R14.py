"""Round 3, R14: settings left from a test's earlier type are cleared on save.

The Test change form hides settings that don't apply to the chosen type (R13), but
their old values were still posted. Choices, a Constant value or Wrap values on the
wrong type made the model refuse the save, and a leftover "Flag the test list" setting
on a non-Boolean test flagged the test list whenever a result was 1 or 0
(signals.check_tli_flag doesn't look at the type). TestForm.clean now clears them,
TestAdmin says which ones it cleared, and the history lists them.
"""

from django.contrib.admin.models import LogEntry
from django.test import TestCase
from django.urls import reverse

from qatrack.accounts.tests.utils import create_user
from qatrack.qa import admin as qa_admin
from qatrack.qa import models
from qatrack.qa.tests import utils as qa_utils


class TestLeftoverTypeSettings(TestCase):

    def setUp(self):
        create_user(is_superuser=True, uname='super', pwd='pwd')
        self.client.login(username='super', password='pwd')
        self.category = qa_utils.create_category()

    def _post(self, test, test_type, **values):
        """Save `test` from its change form as `test_type`, posting `values` as the hidden settings."""
        data = {
            'name': test.name, 'slug': test.slug, 'category': self.category.pk, 'type': test_type,
            'attachment_set-TOTAL_FORMS': 0, 'attachment_set-INITIAL_FORMS': 0, '_continue': '1',
        }
        data.update(values)
        resp = self.client.post(reverse('admin:qa_test_change', args=(test.pk,)), data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'class="errornote"')
        test.refresh_from_db()
        return [str(m) for m in resp.context['messages']]

    def _history(self, test):
        return LogEntry.objects.filter(object_id=str(test.pk)).latest('action_time').get_change_message()

    def test_multiple_choice_to_numerical(self):
        test = qa_utils.create_test(name='mc', test_type=models.MULTIPLE_CHOICE, choices='a,b')
        msgs = self._post(test, models.SIMPLE, choices='a,b')
        self.assertEqual(test.type, models.SIMPLE)
        self.assertIsNone(test.choices)
        self.assertIn("Cleared Choices: these settings don't apply to Simple Numerical tests.", msgs)
        self.assertIn('Choices', self._history(test))

    def test_boolean_flag_is_cleared(self):
        test = qa_utils.create_test(name='yn', test_type=models.BOOLEAN)
        test.flag_when = True
        test.save()
        msgs = self._post(test, models.SIMPLE, flag_when='True')
        self.assertIsNone(test.flag_when)
        self.assertTrue(any('Flag the test list' in m for m in msgs))
        history = self._history(test)
        self.assertIn('Type', history)
        self.assertIn('Flag the test list', history)

    def test_flag_when_false_counts_as_set(self):
        """"When test is No/False" flags results of 0, so it's a setting too."""
        test = qa_utils.create_test(name='yn', test_type=models.BOOLEAN)
        test.flag_when = False
        test.save()
        self._post(test, models.STRING, flag_when='False')
        self.assertIsNone(test.flag_when)

    def test_constant_and_wraparound_values(self):
        test = qa_utils.create_test(name='const', test_type=models.CONSTANT)
        test.constant_value = 0
        test.save()
        msgs = self._post(test, models.WRAPAROUND, constant_value='0', wrap_low='0', wrap_high='360')
        self.assertIsNone(test.constant_value)
        self.assertEqual((test.wrap_low, test.wrap_high), (0, 360))
        self.assertTrue(any(m.startswith('Cleared Constant value:') for m in msgs))

        msgs = self._post(test, models.SIMPLE, wrap_low='0', wrap_high='360')
        self.assertEqual((test.wrap_low, test.wrap_high), (None, None))
        self.assertTrue(any(m.startswith('Cleared Wrap low, Wrap high:') for m in msgs))

    def test_bad_input_in_a_hidden_setting_does_not_block(self):
        test = qa_utils.create_test(name='num', test_type=models.SIMPLE)
        self._post(test, models.SIMPLE, wrap_low='not a number')
        self.assertIsNone(test.wrap_low)

    def test_settings_for_the_chosen_type_are_kept(self):
        test = qa_utils.create_test(name='mc', test_type=models.MULTIPLE_CHOICE, choices='a,b')
        msgs = self._post(test, models.MULTIPLE_CHOICE, choices='a,b,c')
        self.assertEqual(test.choices, 'a,b,c')
        self.assertFalse(any(m.startswith('Cleared') for m in msgs))

        test = qa_utils.create_test(name='yn', test_type=models.BOOLEAN)
        self._post(test, models.BOOLEAN, flag_when='False')
        self.assertIs(test.flag_when, False)

    def test_nothing_to_clear_says_nothing(self):
        test = qa_utils.create_test(name='num', test_type=models.SIMPLE)
        msgs = self._post(test, models.STRING, choices='', flag_when='', wrap_low='')
        self.assertFalse(any(m.startswith('Cleared') for m in msgs))
        self.assertNotIn('Flag the test list', self._history(test))

    def test_add_page(self):
        data = {
            'name': 'New', 'slug': 'new', 'category': self.category.pk, 'type': models.SIMPLE,
            'choices': 'x,y', 'attachment_set-TOTAL_FORMS': 0, 'attachment_set-INITIAL_FORMS': 0, '_save': '1',
        }
        resp = self.client.post(reverse('admin:qa_test_add'), data)
        self.assertEqual(resp.status_code, 302)
        self.assertIsNone(models.Test.objects.get(slug='new').choices)

    def test_every_type_only_setting_is_on_the_form(self):
        fields = qa_admin.TestForm().fields
        for name, types, _label in qa_admin.TEST_TYPE_ONLY_FIELDS:
            self.assertIn(name, fields)
            self.assertTrue(set(types) <= {t for t, _ in models.TEST_TYPE_CHOICES})
