"""
test_browser.py
~~~~~~~~~~~~~~~

Playwright browser tests for the QA module.

Migrated from the Selenium-based ``test_selenium.py``.  Every test class is
marked with ``@pytest.mark.browser`` and relies on the ``PlaywrightTests``
base class from ``qatrack.qatrack_core.tests.playwright_base``.
"""
import time

import pytest
from django.contrib.auth.models import Permission
from django.db import transaction
from django.test import TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from qatrack.accounts.tests.utils import create_group, create_user
from qatrack.qa import models
from qatrack.qa.tests import utils
from qatrack.qatrack_core.dates import format_as_date
from qatrack.qatrack_core.tests.playwright_base import PlaywrightTests
from qatrack.service_log.tests import utils as sl_utils

objects = {

    'Group': {
        'name': 'testGroup',
    },
    'Category': {
        'name': 'testCategory',
        'slug': 'testCategory',
        'description': 'test test test test'
    },
    'Tests': [
        {
            'test_type': models.SIMPLE,
            'name': 'simple',
            'choices': None,
            'constant_value': None,
            'procedure': None
        }, {
            'test_type': models.BOOLEAN,
            'name': 'boolean',
            'choices': None,
            'constant_value': None,
            'procedure': None
        }, {
            'test_type': models.MULTIPLE_CHOICE,
            'name': 'multchoice',
            'choices': '1,2,3,4,5',
            'constant_value': None,
            'procedure': None
        }, {
            'test_type': models.CONSTANT,
            'name': 'constant',
            'choices': None,
            'constant_value': '23.23',
            'procedure': None
        }, {
            'test_type': models.COMPOSITE,
            'name': 'composite',
            'choices': None,
            'constant_value': None,
            'procedure': 'result = constant * simpleNumeric'
        }, {
            'test_type': models.STRING,
            'name': 'string',
            'choices': None,
            'constant_value': None,
            'procedure': None
        }, {
            'test_type': models.STRING_COMPOSITE,
            'name': 'scomposite',
            'choices': None,
            'constant_value': None,
            'procedure': 'result = string + " composite"'
        }, {
            'test_type': models.UPLOAD,
            'name': 'upload',
            'choices': None,
            'constant_value': None,
            'procedure': 'result = FILE[0]'
        }
    ],
    'TestList': {
        'name': 'TestTestList'
    },
    'Modality': {
        'name': 'TestModality'
    },
    'UnitType': {
        'name': 'TestModality',
        'vendor': 'TestVendor'
    },
    'Unit': {
        'name': 'TestUnit',
        'number': '1',
        'date_acceptance': format_as_date(timezone.now())
    },
    'Frequency': {
        'name': 'TestFrequency',
        'nominal_interval': '2',
        'due_interval': '3',
        'window_end': '4'
    },
    'UnitTestCollection': {},
    'absoluteTolerance': {
        'act_low': '-2',
        'tol_low': '-1',
        'tol_high': '1',
        'act_high': '2'
    },
    'percentTolerance': {
        'act_low': '-5',
        'tol_low': '-1',
        'tol_high': '1',
        'act_high': '5'
    },
    'multiChoiceTolerance': {
        'mc_pass_choices': '3',
        'mc_tol_choices': '2,4'
    },
    'refTols': {
        'multipleChoice': {},
        'simpleNumeric': {
            'reference_value': '0'
        },
        'composite': {
            'reference_value': '23.23'
        }
    },
    'statuses': {
        'testStatus': {
            'default': True,
            'requiresApproval': True
        },
        'testApprovalStatus': {
            'dfault': False,
            'requiresApproval': False
        }
    },
}  # yapf: disable


class BaseQATests(PlaywrightTests, TransactionTestCase):

    def setUp(self):
        with transaction.atomic():
            self.password = 'password'
            self.user = create_user(is_superuser=True, uname='user', ******
        super().setUp()

    def login(self):
        self.open('/accounts/login/')
        self.send_keys('id_username', self.user.username)
        self.send_keys('id_password', self.password)
        self.page.locator('button').click()
        expect(self.page.locator('head > title')).to_be_attached()

    def load_main(self):
        self.login()
        self.open('')

    def load_admin(self):
        self.open('/admin/')
        self.send_keys('id_username', self.user.username)
        self.send_keys('id_password', self.password)
        self.page.locator('button').click()
        expect(self.page.locator('head > title')).to_be_attached()


@pytest.mark.browser
class LiveQATests(BaseQATests):

    def setUp(self):
        super().setUp()

    def test_admin_category(self):

        self.load_admin()
        self.page.locator('a[href="/admin/qa/category/"]').click()
        self.click_by_link_text('ADD CATEGORY')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill(objects['Category']['name'])
        self.page.locator('#id_slug').fill(objects['Category']['slug'])
        self.page.locator('#id_description').fill(objects['Category']['description'])
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_tests(self):

        self.load_admin()

        if not utils.exists('qa', 'Category', 'name', objects['Category']['name']):
            utils.create_category(
                name=objects['Category']['name'],
                slug=objects['Category']['slug'],
                description=objects['Category']['description'],
            )

        self.page.get_by_role('link', name='Tests', exact=True).click()
        self.click_by_link_text('ADD TEST')
        expect(self.page.locator('#id_name')).to_be_visible()

        for i, the_test in enumerate(objects['Tests']):
            self.send_keys('id_name', the_test['name'])
            self.send_keys('id_slug', the_test['name'])
            self.select_by_index('id_category', 1)
            self.select_by_value('id_type', the_test['name'])

            if the_test['choices']:
                self.send_keys('id_choices', '1,2,3,4,5')
            if the_test['constant_value']:
                self.send_keys('id_constant_value', '23.23')
            if the_test['procedure']:
                self.page.locator('#calc-procedure-editor > textarea').fill(the_test['procedure'])
                self.page.locator('.submit-row').click()

            if i + 1 == len(objects['Tests']):
                self.page.evaluate("$('input[name=_save]').click();")
            else:
                self.page.evaluate("$('input[name=_addanother]').click();")

            self.wait_for_success()

    def test_admin_testlist(self):

        self.load_admin()

        for the_test in objects['Tests']:
            if not utils.exists('qa', 'Test', 'name', the_test['name']):
                utils.create_test(
                    name=the_test['name'],
                    test_type=the_test['test_type'],
                    choices=the_test['choices'],
                    procedure=the_test['procedure'],
                    constant_value=the_test['constant_value'],
                )

        self.click_by_link_text('Test Lists')
        self.click_by_link_text('ADD TEST LIST')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill(objects['TestList']['name'])
        self.page.locator('#id_slug').fill(objects['TestList']['name'].lower())
        self.page.get_by_role('link', name='Add another Test List Membership').click()
        self.page.get_by_role('link', name='Add another Test List Membership').click()
        self.page.get_by_role('link', name='Add another Test List Membership').click()
        for i, pk in enumerate(models.Test.objects.values_list('pk', flat=True)):
            self.page.locator(f'#id_testlistmembership_set-{i}-test').fill(str(pk))
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_modality(self):

        self.load_admin()
        self.click_by_link_text('Treatment and Imaging Modalities')
        self.click_by_link_text('ADD TREATMENT AND IMAGING MODALITY')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill(objects['Modality']['name'])
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_unittype(self):

        self.load_admin()
        self.click_by_link_text('Unit Types')
        self.click_by_link_text('ADD UNIT TYPE')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill(objects['UnitType']['name'])
        self.page.locator('#id_vendor').fill(objects['UnitType']['vendor'])
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_unit(self):

        if not utils.exists('units', 'UnitType', 'name', objects['UnitType']['name']):
            utils.create_unit_type(
                name=objects['UnitType']['name'], vendor=utils.create_vendor(objects['UnitType']['vendor'])
            )

        if not utils.exists('units', 'Modality', 'name', objects['Modality']['name']):
            utils.create_modality(name=objects['Modality']['name'])

        sl_utils.create_service_area()

        self.load_admin()
        self.click_by_link_text('Units')
        self.click_by_link_text('ADD UNIT')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill(objects['Unit']['name'])
        self.page.locator('#id_number').fill(objects['Unit']['number'])
        self.page.locator('#id_date_acceptance').fill(objects['Unit']['date_acceptance'])
        self.page.locator('#id_service_areas_add_all_link').click()
        self.select_by_index('id_type', 1)
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_frequency(self):

        self.load_admin()
        self.click_by_link_text('Frequencies')
        self.click_by_link_text('ADD FREQUENCY')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill(objects['Frequency']['name'])
        self.page.locator('.recurrence-label').click()
        self.page.locator('.weekly td').nth(0).click()
        self.page.locator('.weekly td').nth(2).click()
        self.page.locator('.weekly td').nth(4).click()
        self.page.locator('#id_window_end').fill(objects['Frequency']['window_end'])
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()
        assert models.Frequency.objects.get(name=objects['Frequency']['name']).nominal_interval < 3

    def test_admin_unittestcollection(self):

        if not utils.exists('auth', 'Group', 'name', objects['Group']['name']):
            create_group(name=objects['Group']['name'])

        if not utils.exists('units', 'Unit', 'name', objects['Modality']['name']):
            utils.create_unit(name=objects['Modality']['name'], number=objects['Unit']['number'])

        if not utils.exists('qa', 'Frequency', 'name', objects['Frequency']['name']):
            utils.create_frequency(name=objects['Frequency']['name'])

        if not utils.exists('qa', 'TestList', 'name', objects['TestList']['name']):
            utils.create_test_list(name=objects['TestList']['name'])

        self.load_admin()
        self.click_by_link_text('Assign Test Lists to Units')
        self.click_by_link_text('ADD UNIT TEST COLLECTION')
        expect(self.page.locator('#id_unit')).to_be_visible()

        self.select_by_index('id_unit', -1)
        self.select_by_index('id_frequency', -1)
        self.select_by_index('id_assigned_to', 0)
        self.select_by_index('id_content_type', 1)
        self.page.locator('#id_visible_to_from > option:nth-child(1)').click()
        self.page.locator('#id_visible_to_add_link').click()

        self.page.locator('#select2-generic_object_id-container').click()
        self.page.locator('#select2-generic_object_id-container').click()
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_tolerances(self):

        # Add absolute tolerance
        self.load_admin()
        self.click_by_link_text('Tolerances')
        self.click_by_link_text('ADD TOLERANCE')
        expect(self.page.locator('#id_type')).to_be_visible()
        self.select_by_index('id_type', 1)
        self.page.locator('#id_act_low').fill(objects['absoluteTolerance']['act_low'])
        self.page.locator('#id_tol_low').fill(objects['absoluteTolerance']['tol_low'])
        self.page.locator('#id_tol_high').fill(objects['absoluteTolerance']['tol_high'])
        self.page.locator('#id_act_high').fill(objects['absoluteTolerance']['act_high'])
        self.page.locator('[name="_addanother"]').click()
        self.wait_for_success()

        # Add percentage tolerance
        expect(self.page.locator('#id_type')).to_be_visible()
        self.select_by_index('id_type', 1)
        self.page.locator('#id_act_low').fill(objects['percentTolerance']['act_low'])
        self.page.locator('#id_tol_low').fill(objects['percentTolerance']['tol_low'])
        self.page.locator('#id_tol_high').fill(objects['percentTolerance']['tol_high'])
        self.page.locator('#id_act_high').fill(objects['percentTolerance']['act_high'])
        self.page.locator('[name="_addanother"]').click()
        self.wait_for_success()

        # Add multi tolerance
        expect(self.page.locator('#id_type')).to_be_visible()
        self.select_by_index('id_type', 3)
        self.page.locator('#id_mc_pass_choices').fill(objects['multiChoiceTolerance']['mc_pass_choices'])
        self.page.locator('#id_mc_tol_choices').fill(objects['multiChoiceTolerance']['mc_tol_choices'])
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_set_ref_tols(self):

        utils.create_tolerance(tol_type=models.MULTIPLE_CHOICE, mc_pass_choices='a,b')
        utils.create_tolerance()

        for the_test in objects['Tests']:
            if the_test['test_type'] == models.MULTIPLE_CHOICE:
                if not utils.exists('qa', 'Test', 'name', the_test['name']):
                    mult_test = utils.create_test(
                        test_type=models.MULTIPLE_CHOICE, choices=the_test['choices'], name=the_test['name']
                    )
            elif the_test['test_type'] == models.SIMPLE:
                if not utils.exists('qa', 'Test', 'name', the_test['name']):
                    simp_test = utils.create_test(test_type=models.SIMPLE, name=the_test['name'])
            elif the_test['test_type'] == models.COMPOSITE:
                if not utils.exists('qa', 'Test', 'name', the_test['name']):
                    comp_test = utils.create_test(test_type=models.COMPOSITE, name=the_test['name'])

        if not utils.exists('qa', 'TestList', 'name', objects['TestList']['name']):
            test_list = utils.create_test_list(objects['TestList']['name'])
            utils.create_test_list_membership(test_list=test_list, test=mult_test)
            utils.create_test_list_membership(test_list=test_list, test=simp_test)
            utils.create_test_list_membership(test_list=test_list, test=comp_test)

        utils.create_unit_test_collection(test_collection=test_list)

        self.load_admin()
        self.click_by_link_text('Set References & Tolerances')
        self.click_by_link_text(mult_test.name)
        expect(self.page.locator('#id_tolerance')).to_be_visible()
        self.select_by_index('id_tolerance', 1)
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

        self.page.get_by_role('link', name='simple').click()
        self.select_by_index('id_tolerance', 1)
        self.page.locator('#id_reference_value').fill('0')
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

        self.page.get_by_role('link', name='composite').click()
        self.select_by_index('id_tolerance', 1)
        self.page.locator('#id_reference_value').fill('23.23')
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()

    def test_admin_statuses(self):

        self.load_admin()
        expect(self.page.locator("a[href*='testinstancestatus']")).to_be_visible()
        self.page.locator("a[href*='testinstancestatus']").click()
        self.click_by_link_text('ADD TEST INSTANCE STATUS')
        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill('testStatus')
        self.page.locator('#id_is_default').click()
        self.page.locator('[name="_addanother"]').click()
        self.wait_for_success()

        expect(self.page.locator('#id_name')).to_be_visible()
        self.page.locator('#id_name').fill('testApprovalStatus')
        self.page.locator('#id_requires_review').click()
        self.page.locator('[name="_save"]').click()
        self.wait_for_success()


@pytest.mark.browser
class TestPerformQC(BaseQATests):

    def setUp(self):
        with transaction.atomic():
            super().setUp()

            self.unit = utils.create_unit()
            self.group = utils.create_group()
            for p in Permission.objects.all():
                self.group.permissions.add(p)
            self.user.groups.add(self.group)
            self.test_list = utils.create_test_list()

            self.tnum_1 = utils.create_test(name='test1')
            self.tnum_2 = utils.create_test(name='test2')
            self.tcomp = utils.create_test(name='testc', test_type=models.COMPOSITE)
            self.tcomp.calculation_procedure = 'result = test1 + test2 + 2'
            self.tcomp.save()

            self.tdate = utils.create_test(name='testdate', test_type=models.DATE)
            self.tdatetime = utils.create_test(name='testdatetime', test_type=models.DATETIME)

            self.tmult = utils.create_test(name='testmult', choices='choicea,choiceb', test_type=models.MULTIPLE_CHOICE)
            self.tstring = utils.create_test(name='teststring', test_type=models.STRING)
            self.tstringcomp = utils.create_test(name='teststringcomp', test_type=models.STRING_COMPOSITE)
            self.tstringcomp.calculation_procedure = 'teststringcomp = teststring + testmult'
            self.tstringcomp.save()

            all_tests = [
                self.tnum_1,
                self.tnum_2,
                self.tcomp,
                self.tdate,
                self.tdatetime,
                self.tmult,
                self.tstring,
                self.tstringcomp,
            ]

            for o, t in enumerate(all_tests):
                utils.create_test_list_membership(self.test_list, t, order=o)

            self.utc = utils.create_unit_test_collection(unit=self.unit, test_collection=self.test_list)

            self.utc.visible_to.add(self.group)
            self.url = reverse('perform_qa', kwargs={'pk': self.utc.pk})
            self.status = models.TestInstanceStatus.objects.create(
                name='foo',
                slug='foo',
                is_default=True,
            )

            sl_utils.create_service_event_status(is_default=True)
            sl_utils.create_unit_service_area(self.utc.unit)
            sl_utils.create_service_type()

    def test_ok_on_load(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""
        with transaction.atomic():
            self.login()
            self.open(self.url)
            assert self.page.locator('.qa-status.btn-danger').count() == 0

    def fill_testlist(self):

        self.login()
        self.open(self.url)
        inputs = self.page.locator('.qa-input').all()[:3]
        inputs[0].fill('1')
        inputs[1].fill('2')
        inputs[1].press('Tab')
        self.page.wait_for_function("typeof jQuery !== 'undefined' ? jQuery.active == 0 : true")
        self.click_by_css_selector('.choose-date')
        self.page.locator('.open .today').wait_for()
        self.click_by_css_selector('.open .today')

        self.click_by_css_selector('.choose-datetime')
        self.page.locator('.open .today').wait_for()
        self.click_by_css_selector('.open .today')

        self.click_by_css_selector('body')

        option = self.page.locator('select.qa-input option').last
        option.click()

        self.page.locator('.qa-string .qa-input').fill('test')
        self.click_by_css_selector('body')
        self.page.wait_for_function("typeof jQuery !== 'undefined' ? jQuery.active == 0 : true")

    def test_perform_ok(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        self.fill_testlist()
        inputs = self.page.locator('.qa-input').all()[:3]

        assert int(float(inputs[2].input_value())) == 5
        assert models.TestListInstance.objects.count() == 0
        self.click('submit-qa')
        expect(self.page.locator('.alert-success')).to_be_visible()
        self.page.wait_for_function("typeof jQuery !== 'undefined' ? jQuery.active == 0 : true")

        assert models.TestListInstance.objects.count() == 1
        assert models.TestListInstance.objects.latest('pk').include_for_scheduling

        assert models.TestInstance.objects.filter(unit_test_info__test__type='simple')[0].value == 1
        assert models.TestInstance.objects.filter(unit_test_info__test__type='simple')[1].value == 2
        assert models.TestInstance.objects.get(unit_test_info__test__type='composite').value == 5
        now = timezone.now()
        date = timezone.localtime(now).date()
        assert models.TestInstance.objects.get(unit_test_info__test__type='date').date_value == date
        dt = timezone.localtime(now).replace(hour=12, minute=0, second=0, microsecond=0)
        assert models.TestInstance.objects.get(unit_test_info__test__type='datetime').datetime_value == dt
        assert models.TestInstance.objects.get(unit_test_info__test__type='string').string_value == 'test'
        assert models.TestInstance.objects.get(unit_test_info__test__type='scomposite').string_value == 'testchoiceb'
        assert models.TestInstance.objects.get(unit_test_info__test__type='multchoice').string_value == 'choiceb'

    def test_perform_ok_therapist(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        self.group.permissions.clear()
        self.user.is_superuser = False
        self.user.save()
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(models.TestListInstance)
        perm, _ = Permission.objects.get_or_create(
            codename='add_testlistinstance', content_type=ct, defaults={'name': 'Can add test list instance'}
        )
        self.group.permissions.add(perm)
        self.fill_testlist()
        inputs = self.page.locator('.qa-input').all()[:3]

        assert int(float(inputs[2].input_value())) == 5
        assert models.TestListInstance.objects.count() == 0
        self.click('submit-qa')
        expect(self.page.locator('.alert-success')).to_be_visible()
        self.page.wait_for_function("typeof jQuery !== 'undefined' ? jQuery.active == 0 : true")

        assert models.TestListInstance.objects.count() == 1
        assert models.TestListInstance.objects.latest('pk').include_for_scheduling

        assert models.TestInstance.objects.filter(unit_test_info__test__type='simple')[0].value == 1
        assert models.TestInstance.objects.filter(unit_test_info__test__type='simple')[1].value == 2
        assert models.TestInstance.objects.get(unit_test_info__test__type='composite').value == 5
        now = timezone.now()
        date = timezone.localtime(now).date()
        assert models.TestInstance.objects.get(unit_test_info__test__type='date').date_value == date
        dt = timezone.localtime(now).replace(hour=12, minute=0, second=0, microsecond=0)
        assert models.TestInstance.objects.get(unit_test_info__test__type='datetime').datetime_value == dt
        assert models.TestInstance.objects.get(unit_test_info__test__type='string').string_value == 'test'
        assert models.TestInstance.objects.get(unit_test_info__test__type='scomposite').string_value == 'testchoiceb'
        assert models.TestInstance.objects.get(unit_test_info__test__type='multchoice').string_value == 'choiceb'

    def test_comment(self):
        """tests present"""
        self.fill_testlist()
        self.page.locator('.revealcomment').first.click()
        self.send_keys('id_form-0-comment', 'testticomment')
        self.page.locator('.revealcomment').first.click()

        self.click('submit-qa')
        expect(self.page.locator('.alert-success')).to_be_visible()
        assert models.TestInstance.objects.filter(comment='testticomment').count() == 1

    def test_set_in_progress(self):
        """tests present"""
        self.fill_testlist()

        self.click('in-progress-container')
        self.click('submit-qa')
        expect(self.page.locator('.alert-success')).to_be_visible()
        assert models.TestListInstance.objects.in_progress().count() == 1

    def test_perform_and_review(self):
        """Ensure that we can go through a full perform->review cycle"""

        utils.create_status(name='reviewed', slug='reviewed', is_default=False, requires_review=False)
        self.fill_testlist()
        self.click('submit-qa')
        expect(self.page.locator('.alert-success')).to_be_visible()

        self.open('/qc/session/unreviewed/')

        self.click_by_link_text('Review')
        self.select_by_text('bot-status-select', 'reviewed')

        self.send_keys('id_comment', 'testlistcomment')
        self.click('post-comment')
        assert models.Comment.objects.count() == 1

        assert models.TestListInstance.objects.unreviewed().count() == 1
        self.click('submit-review')
        expect(self.page.locator('.alert-success')).to_be_visible()
        assert models.TestListInstance.objects.unreviewed().count() == 0

    def test_perform_and_initiate_se(self):
        """Ensure that we can go through a full perform->initiate service event cycle"""

        self.fill_testlist()
        self.click('init-se-container')
        self.click('submit-qa')

        expect(self.page.locator('.alert-success')).to_be_visible()

        self.page.evaluate("$('#id_datetime_service').focus()")
        self.click_by_css_selector('.today')
        self.select_by_index('id_service_area_field_fake', 1)
        self.select_by_index('id_service_type', 1)
        self.send_keys('id_problem_description', 'Problem!')
        self.click('save-se')
        assert models.TestListInstance.objects.first().serviceevents_initiated.count() == 1

    def test_autosave(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        self.login()
        self.open(self.url)
        inputs = self.page.locator('.qa-input').all()[:3]
        inputs[0].fill('1')
        assert models.AutoSave.objects.count() == 0
        inputs[0].press('Enter')
        time.sleep(4.2)  # auto save is debounced with a 4s interval
        assert models.AutoSave.objects.count() == 1

    def test_load_autosave(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        tl2 = utils.create_test_list(name='day 2')
        utils.create_test_list_membership(tl2, test=self.tnum_1)
        cycle = utils.create_cycle([self.test_list, tl2])
        utc = utils.create_unit_test_collection(
            unit=self.utc.unit, test_collection=cycle, assigned_to=self.utc.assigned_to
        )

        tz = timezone.get_current_timezone()
        auto = models.AutoSave.objects.create(
            unit_test_collection=utc,
            test_list=tl2,
            day=1,
            work_started=timezone.datetime(1980, 5, 12, 12).replace(tzinfo=tz),
            work_completed=timezone.datetime(1980, 5, 12, 12, 1).replace(tzinfo=tz),
            created_by=self.user,
            modified_by=self.user,
            data={
                'tests': {
                    'test1': 1,
                },
                'comments': {
                    'test1': 'test comment',
                },
                'skips': {
                    'test1': False,
                },
                'tli_comment': 'test list instance comment'
            }
        )

        self.login()

        url = reverse('perform_qa', kwargs={'pk': utc.pk})
        self.open(url + '?autosave_id=%d&day=%d' % (auto.pk, auto.day + 1))

        inputs = self.page.locator('.qa-input').all()[:3]
        title = 'Perform %s : day 2' % utc.unit.name
        box_titles = [el.text_content() for el in self.page.locator('.box-title').all()]
        assert title in box_titles
        assert float(inputs[0].input_value()) == 1
        assert self.page.locator('#id_work_started').input_value() == '12 May 1980 12:00'
        assert self.page.locator('#id_work_completed').input_value() == '12 May 1980 12:01'
        assert self.page.locator('#id_work_duration').input_value() == '0hr:01min'
        assert self.page.locator('#id_form-0-comment').input_value() == 'test comment'
        assert self.page.locator('#id_comment').input_value() == 'test list instance comment'

    def test_submit_autosave(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        tl2 = utils.create_test_list(name='day 2')
        utils.create_test_list_membership(tl2, test=self.tnum_1)
        cycle = utils.create_cycle([self.test_list, tl2])
        utc = utils.create_unit_test_collection(
            unit=self.utc.unit, test_collection=cycle, assigned_to=self.utc.assigned_to
        )

        tz = timezone.get_current_timezone()
        auto = models.AutoSave.objects.create(
            unit_test_collection=utc,
            test_list=tl2,
            day=1,
            work_started=timezone.datetime(1980, 5, 12, 12).replace(tzinfo=tz),
            work_completed=timezone.datetime(1980, 5, 12, 12, 1).replace(tzinfo=tz),
            created_by=self.user,
            modified_by=self.user,
            data={
                'tests': {
                    'test1': 1,
                },
                'comments': {
                    'test1': 'test comment',
                },
                'skips': {
                    'test1': False,
                },
                'tli_comment': 'test list instance comment'
            }
        )

        self.login()

        url = reverse('perform_qa', kwargs={'pk': utc.pk})
        self.open(url + '?autosave_id=%d&day=%d' % (auto.pk, auto.day + 1))

        self.click('submit-qa')

        assert models.AutoSave.objects.filter(pk=auto.pk).count() == 0


@pytest.mark.browser
class TestReviewQC(BaseQATests):

    def setUp(self):
        with transaction.atomic():
            super().setUp()

            self.unreviewed = utils.create_status(name='Unreviewed', slug='unreviewed')
            self.reviewed = utils.create_status(
                name='Approved', slug='approved', is_default=False, requires_review=False
            )
            utils.create_test_instance()

            self.url = '/qc/session/unreviewed/'

    @override_settings(REVIEW_BULK=True)
    def test_review_ok(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""
        with transaction.atomic():
            self.login()
            self.open(self.url)
            self.page.locator('.test-selected-toggle').first.click()
            self.select_by_text('bulk-status', 'Approved')
            self.click('submit-review')
            assert models.TestListInstance.objects.unreviewed().count() == 1

            self.click('confirm-update')
            expect(self.page.locator('.alert-success')).to_be_visible()
            assert models.TestListInstance.objects.unreviewed().count() == 0
