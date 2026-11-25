import time

import pytest
from django.contrib.auth.models import Permission
from django.db import transaction
from django.test import TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format, get_format
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as e_c

from qatrack.accounts.tests.utils import create_group, create_user
from qatrack.qa import models
from qatrack.qa.tests import utils
from qatrack.qatrack_core.dates import format_as_date
from qatrack.qatrack_core.tests.live import SeleniumTests
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


class BaseQATests(SeleniumTests, TransactionTestCase):

    def setUp(self):
        with transaction.atomic():
            self.password = 'password'
            self.user = create_user(pwd=self.password)

    def login(self):
        self.open("/accounts/login/")
        self.send_keys("id_username", self.user.username)
        self.send_keys("id_password", self.password)
        self.driver.find_element(By.CSS_SELECTOR, 'button').click()

        # Wait for proof that the login POST was handled and the redirect has
        # rendered. The logout link is inside {% if user.is_authenticated %}
        # in site_base.html, so its presence means both.
        #
        # This used to wait for "head > title", which every page has -
        # including the login page still on screen. It was satisfied
        # immediately, before the POST had even been sent, so a slow round
        # trip left the test unauthenticated. It then failed later, somewhere
        # else, as a timeout waiting for an element that only exists when
        # logged in - which looks like an unrelated flake.
        self.wait.until(
            e_c.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="logout"]'))
        )

    def load_main(self):
        self.login()
        self.open("")

    def load_admin(self):
        self.open("/admin/")
        self.send_keys("id_username", self.user.username)
        self.send_keys("id_password", self.password)
        self.driver.find_element(By.CSS_SELECTOR, 'button').click()

        # Same vacuous wait as login() had, same fix. #user-tools is the
        # admin header's account block, rendered only once authenticated -
        # measured absent before the click and present after. The admin
        # cannot use the logout link login() waits for: Django 4.1 turned
        # admin logout into a POST form, so there is no logout href here.
        self.wait.until(e_c.presence_of_element_located((By.CSS_SELECTOR, '#user-tools')))


@pytest.mark.selenium
class LiveQATests(BaseQATests):

    def setUp(self):

        super().setUp()

    def test_admin_category(self):

        self.load_admin()
        self.driver.find_element(By.XPATH, '//a[@href="/admin/qa/category/"]').click()
        self.click_by_link_text("ADD CATEGORY")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys(objects['Category']['name'])
        self.driver.find_element(By.ID, 'id_slug').send_keys(objects['Category']['slug'])
        self.driver.find_element(By.ID, 'id_description').send_keys(objects['Category']['description'])
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_tests(self):

        self.load_admin()

        if not utils.exists('qa', 'Category', 'name', objects['Category']['name']):
            utils.create_category(
                name=objects['Category']['name'],
                slug=objects['Category']['slug'],
                description=objects['Category']['description'],
            )

        self.driver.find_element(By.LINK_TEXT, 'Tests').click()
        self.click_by_link_text("ADD TEST")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        # for i in range(len(objects['Tests'])):

        for i in range(len(objects['Tests'])):
            # the_test = objects['Tests'][i]
            the_test = objects['Tests'][i]
            self.send_keys('id_name', the_test['name'])
            self.send_keys('id_slug', the_test['name'])
            self.select_by_index('id_category', 1)
            self.select_by_value('id_type', the_test['name'])
            # NOT wait_for_ajax(): choosing the test type triggers a purely
            # client-side re-render of the type-dependent fields (choices,
            # constant value, the calculation procedure editor). No request
            # is in flight, so an AJAX wait returns immediately and the
            # fields below are filled before they exist - the save then
            # fails and wait_for_success() times out.
            self.wait_for_ajax()
            time.sleep(0.1)

            if the_test['choices']:
                self.send_keys('id_choices', '1,2,3,4,5')
            if the_test['constant_value']:
                self.send_keys('id_constant_value', '23.23')
            if the_test['procedure']:
                time.sleep(1)
                self.driver.find_element(By.CSS_SELECTOR, '#calc-procedure-editor > textarea').send_keys(
                    the_test['procedure'],
                )
                self.driver.find_element(By.CSS_SELECTOR, '.submit-row').click()

            # Firefox webdriver being weird with clicks. Had to use javascript here:
            if i + 1 == len(objects['Tests']):
                self.driver.execute_script("$('input[name=_save]').click();")
            else:
                self.driver.execute_script("$('input[name=_addanother]').click();")

            for i in range(3):
                try:
                    self.wait_for_success()
                    break
                except:  # noqa: E722
                    if i == 2:
                        raise
                    else:
                        time.sleep(1)

    def test_admin_testlist(self):

        self.load_admin()

        for i in range(len(objects['Tests'])):
            the_test = objects['Tests'][i]
            if not utils.exists('qa', 'Test', 'name', the_test['name']):
                utils.create_test(
                    name=the_test['name'],
                    test_type=the_test['test_type'],
                    choices=the_test['choices'],
                    procedure=the_test['procedure'],
                    constant_value=the_test['constant_value'],
                )

        self.click_by_link_text("Test Lists")
        self.click_by_link_text("ADD TEST LIST")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys(objects['TestList']['name'])
        self.driver.find_element(By.ID, 'id_slug').send_keys(objects['TestList']['name'].lower())
        self.driver.find_element(By.LINK_TEXT, 'Add another Test List Membership').click()
        self.driver.find_element(By.LINK_TEXT, 'Add another Test List Membership').click()
        self.driver.find_element(By.LINK_TEXT, 'Add another Test List Membership').click()
        for i, pk in enumerate(models.Test.objects.values_list("pk", flat=True)):
            self.driver.find_element(By.ID, 'id_testlistmembership_set-' + str(i) + '-test').send_keys(str(pk))
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_modality(self):

        self.load_admin()
        self.click_by_link_text("Treatment and Imaging Modalities")
        self.click_by_link_text("ADD TREATMENT AND IMAGING MODALITY")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys(objects['Modality']['name'])
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_unittype(self):

        self.load_admin()
        self.click_by_link_text("Unit Types")
        self.click_by_link_text("ADD UNIT TYPE")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys(objects['UnitType']['name'])
        self.driver.find_element(By.ID, 'id_vendor').send_keys(objects['UnitType']['vendor'])
        self.driver.find_element(By.NAME, '_save').click()
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
        self.click_by_link_text("Units")
        self.click_by_link_text("ADD UNIT")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys(objects['Unit']['name'])
        self.driver.find_element(By.ID, 'id_number').send_keys(objects['Unit']['number'])
        self.driver.find_element(By.ID, 'id_date_acceptance').send_keys(objects['Unit']['date_acceptance'])
        self.driver.find_element(By.CSS_SELECTOR, '#id_service_areas_add_all_link').click()
        self.select_by_index("id_type", 1)
        # self.driver.find_element(By.ID,'id_modalities_add_all_link').click()
        # self.driver.find_element(By.ID,'id_hours_monday').send_keys('800')
        # self.driver.find_element(By.ID,'id_hours_tuesday').send_keys('800')
        # self.driver.find_element(By.ID,'id_hours_wednesday').send_keys('800')
        # self.driver.find_element(By.ID,'id_hours_thursday').send_keys('800')
        # self.driver.find_element(By.ID,'id_hours_friday').send_keys('800')
        # self.driver.find_element(By.ID,'id_hours_saturday').send_keys('800')
        # self.driver.find_element(By.ID,'id_hours_sunday').send_keys('800')
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_frequency(self):

        self.load_admin()
        self.click_by_link_text("Frequencies")
        self.click_by_link_text("ADD FREQUENCY")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys(objects['Frequency']['name'])
        self.driver.find_element(By.CLASS_NAME, "recurrence-label").click()
        cells = self.wait_for_elements(By.CSS_SELECTOR, ".weekly td", minimum=5)
        cells[0].click()
        cells[2].click()
        cells[4].click()
        self.driver.find_element(By.ID, 'id_window_end').send_keys(objects['Frequency']['window_end'])
        self.driver.find_element(By.NAME, '_save').click()
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
        self.click_by_link_text("Assign Test Lists to Units")
        self.click_by_link_text('ADD UNIT TEST COLLECTION')
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_unit')))

        self.select_by_index("id_unit", -1)
        self.wait_for_ajax()
        self.select_by_index("id_frequency", -1)
        self.select_by_index("id_assigned_to", 0)
        self.select_by_index("id_content_type", 1)
        self.driver.find_element(By.CSS_SELECTOR, '#id_visible_to_from > option:nth-child(1)').click()
        self.driver.find_element(By.CSS_SELECTOR, '#id_visible_to_add_link').click()

        self.wait_for_ajax()

        self.driver.find_element(By.ID, 'select2-generic_object_id-container').click()
        self.driver.find_element(By.ID, 'select2-generic_object_id-container').click()
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_tolerances(self):

        # Add absolute tolerance
        self.load_admin()
        self.click_by_link_text('Tolerances')
        self.click_by_link_text('ADD TOLERANCE')
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_type')))
        self.select_by_index("id_type", 1)
        self.driver.find_element(By.ID, 'id_act_low').send_keys(objects['absoluteTolerance']['act_low'])
        self.driver.find_element(By.ID, 'id_tol_low').send_keys(objects['absoluteTolerance']['tol_low'])
        self.driver.find_element(By.ID, 'id_tol_high').send_keys(objects['absoluteTolerance']['tol_high'])
        self.driver.find_element(By.ID, 'id_act_high').send_keys(objects['absoluteTolerance']['act_high'])
        self.driver.find_element(By.NAME, '_addanother').click()
        self.wait_for_success()

        # Add percentage tolerance
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_type')))
        self.select_by_index("id_type", 1)
        self.driver.find_element(By.ID, 'id_act_low').send_keys(objects['percentTolerance']['act_low'])
        self.driver.find_element(By.ID, 'id_tol_low').send_keys(objects['percentTolerance']['tol_low'])
        self.driver.find_element(By.ID, 'id_tol_high').send_keys(objects['percentTolerance']['tol_high'])
        self.driver.find_element(By.ID, 'id_act_high').send_keys(objects['percentTolerance']['act_high'])
        self.driver.find_element(By.NAME, '_addanother').click()
        self.wait_for_success()

        # Add multi tolerance
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_type')))
        self.select_by_index("id_type", 3)
        self.driver.find_element(By.ID,
                                 'id_mc_pass_choices').send_keys(objects['multiChoiceTolerance']['mc_pass_choices'])
        self.driver.find_element(By.ID,
                                 'id_mc_tol_choices').send_keys(objects['multiChoiceTolerance']['mc_tol_choices'])
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_set_ref_tols(self):

        utils.create_tolerance(tol_type=models.MULTIPLE_CHOICE, mc_pass_choices="a,b")

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
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_tolerance')))
        self.select_by_index("id_tolerance", 1)
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

        self.driver.find_element(By.LINK_TEXT, 'simple').click()
        self.select_by_index("id_tolerance", 1)
        self.driver.find_element(By.ID, 'id_reference_value').send_keys('0')
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

        self.driver.find_element(By.LINK_TEXT, 'composite').click()
        self.select_by_index("id_tolerance", 1)
        self.driver.find_element(By.ID, 'id_reference_value').send_keys('23.23')
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def test_admin_statuses(self):

        self.load_admin()
        self.wait.until(e_c.presence_of_element_located((By.XPATH, "//a[contains(@href,'testinstancestatus')]")))
        self.driver.find_element(By.XPATH, "//a[contains(@href,'testinstancestatus')]").click()
        self.click_by_link_text('ADD TEST INSTANCE STATUS')
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys('testStatus')
        self.driver.find_element(By.ID, 'id_is_default').click()
        self.driver.find_element(By.NAME, '_addanother').click()
        self.wait_for_success()

        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_name')))
        self.driver.find_element(By.ID, 'id_name').send_keys('testApprovalStatus')
        self.driver.find_element(By.ID, 'id_requires_review').click()
        self.driver.find_element(By.NAME, '_save').click()
        self.wait_for_success()

    def rest(self):

        self.load_main()

        # Perform test
        self.click_by_link_text('TestUnit')
        self.click_by_link_text('Perform')

        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_form-0-value')))
        basic = self.driver.find_element(By.ID, 'id_form-0-value')
        boolean = self.driver.find_element(By.NAME, 'form-1-value')
        basic.send_keys('3')
        boolean.click()
        self.wait.until(
            e_c.presence_of_element_located(
                (By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[1]/td[5][contains(text(), "ACT(3.00)")]')
            )
        )

        basic.send_keys(Keys.BACKSPACE, '2')
        boolean.click()
        self.wait.until(
            e_c.presence_of_element_located(
                (By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[1]/td[5][contains(text(), "TOL(2.00)")]')
            )
        )

        basic.send_keys(Keys.BACKSPACE, '1')
        boolean.click()
        self.wait.until(
            e_c.presence_of_element_located(
                (By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[1]/td[5][contains(text(), "OK(1.00)")]')
            )
        )

        self.wait.until(
            e_c.presence_of_element_located(
                (By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[13]/td[5][contains(text(), "OK(0.0%)")]')
            )
        )

        basic.send_keys(Keys.BACKSPACE, '1.06')
        boolean.click()
        self.wait.until(
            e_c.presence_of_element_located(
                (By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[13]/td[5][contains(text(), "ACT(6.0%)")]')
            )
        )

        basic.send_keys(Keys.BACKSPACE, '5')
        boolean.click()
        self.wait.until(
            e_c.presence_of_element_located(
                (By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[13]/td[5][contains(text(), "TOL(5.0%)")]')
            )
        )

        basic.send_keys(Keys.BACKSPACE, Keys.BACKSPACE, Keys.BACKSPACE)
        boolean.click()
        # time.sleep(1)

        multi = self.driver.find_element(By.ID, 'id_form-2-string_value')
        multi.click()
        multi.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
        self.assertTrue(
            self.driver.find_element(By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[7]/td[5]').text == 'ACT'
        )
        multi.click()
        multi.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
        self.assertTrue(
            self.driver.find_element(By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[7]/td[5]').text == 'TOL'
        )
        multi.click()
        multi.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
        self.assertTrue(
            self.driver.find_element(By.XPATH, '//*[@id="perform-qa-table"]/tbody/tr[7]/td[5]').text == 'OK'
        )

        self.driver.find_element(By.ID, 'id_form-5-string_value').send_keys('a string')
        boolean.click()
        self.wait.until(
            e_c.text_to_be_present_in_element_value((By.ID, 'id_form-6-string_value'), 'a string composite')
        )

        self.driver.find_element(By.ID, 'id_form-7-skipped').click()

        self.driver.find_element(By.ID, 'submit-qa').click()

        self.wait.until(e_c.presence_of_element_located((By.XPATH, '//div[contains(text(), "Showing 1 to 1")]')))
        self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Review Data').click()
        self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Unreviewed Visible To Your Groups').click()
        self.click_by_link_text('Review')

        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_testinstance_set-0-status')))
        self.driver.find_element(By.ID, 'bulk-status').click()
        self.driver.find_element(By.ID, 'bulk-status').send_keys(Keys.ARROW_DOWN, Keys.ARROW_DOWN, Keys.ENTER)

        self.driver.find_element(By.XPATH, '//button[@type = "submit"]').click()

        self.wait.until(
            e_c.presence_of_element_located((By.XPATH, '//td[contains(text(), "No data available in table")]'))
        )


@pytest.mark.selenium
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

            self.tnum_1 = utils.create_test(name="test1")
            self.tnum_2 = utils.create_test(name="test2")
            self.tcomp = utils.create_test(name="testc", test_type=models.COMPOSITE)
            self.tcomp.calculation_procedure = "result = test1 + test2 + 2"
            self.tcomp.save()

            self.tdate = utils.create_test(name="testdate", test_type=models.DATE)
            self.tdatetime = utils.create_test(name="testdatetime", test_type=models.DATETIME)

            self.tmult = utils.create_test(name="testmult", choices="choicea,choiceb", test_type=models.MULTIPLE_CHOICE)
            self.tstring = utils.create_test(name="teststring", test_type=models.STRING)
            self.tstringcomp = utils.create_test(name="teststringcomp", test_type=models.STRING_COMPOSITE)
            self.tstringcomp.calculation_procedure = "teststringcomp = teststring + testmult"
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
            self.url = reverse("perform_qa", kwargs={'pk': self.utc.pk})
            self.status = models.TestInstanceStatus.objects.create(
                name="foo",
                slug="foo",
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
            assert len(self.driver.find_elements(By.CSS_SELECTOR, ".qa-status.btn-danger")) == 0

    def fill_testlist(self):

        self.login()
        self.open(self.url)
        inputs = self.wait_for_elements(By.CLASS_NAME, "qa-input", minimum=2)[:3]
        inputs[0].send_keys(1)
        inputs[1].send_keys(2)
        inputs[1].send_keys(Keys.TAB)
        self.wait.until(lambda d: d.execute_script("return typeof jQuery !== 'undefined' ? jQuery.active == 0 : true"))
        self.click_by_css_selector(".choose-date")
        self.wait.until(e_c.element_to_be_clickable((By.CSS_SELECTOR, ".open .today")))
        self.click_by_css_selector(".open .today")

        self.click_by_css_selector(".choose-datetime")
        self.wait.until(e_c.element_to_be_clickable((By.CSS_SELECTOR, ".open .today")))
        self.click_by_css_selector(".open .today")

        self.click_by_css_selector("body")

        option = self.wait_for_elements(By.CSS_SELECTOR, "select.qa-input option")[-1]
        option.click()

        self.driver.find_element(By.CSS_SELECTOR, ".qa-string .qa-input").send_keys("test")
        self.click_by_css_selector("body")
        self.wait.until(lambda d: d.execute_script("return typeof jQuery !== 'undefined' ? jQuery.active == 0 : true"))
    def test_perform_ok(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        self.fill_testlist()
        inputs = self.wait_for_elements(By.CLASS_NAME, "qa-input", minimum=2)[:3]

        assert int(float(inputs[2].get_attribute("value"))) == 5
        assert models.TestListInstance.objects.count() == 0
        self.click("submit-qa")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        self.wait.until(lambda d: d.execute_script("return typeof jQuery !== 'undefined' ? jQuery.active == 0 : true"))

        assert models.TestListInstance.objects.count() == 1
        assert models.TestListInstance.objects.latest("pk").include_for_scheduling

        assert models.TestInstance.objects.filter(unit_test_info__test__type="simple")[0].value == 1
        assert models.TestInstance.objects.filter(unit_test_info__test__type="simple")[1].value == 2
        assert models.TestInstance.objects.get(unit_test_info__test__type="composite").value == 5
        now = timezone.now()
        date = timezone.localtime(now).date()
        assert models.TestInstance.objects.get(unit_test_info__test__type="date").date_value == date
        dt = timezone.localtime(now).replace(hour=12, minute=0, second=0, microsecond=0)
        assert models.TestInstance.objects.get(unit_test_info__test__type="datetime").datetime_value == dt
        assert models.TestInstance.objects.get(unit_test_info__test__type="string").string_value == "test"
        assert models.TestInstance.objects.get(unit_test_info__test__type="scomposite").string_value == "testchoiceb"
        assert models.TestInstance.objects.get(unit_test_info__test__type="multchoice").string_value == "choiceb"

    def test_perform_ok_therapist(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        self.group.permissions.clear()
        self.user.is_superuser = False
        self.user.save()
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(models.TestListInstance)
        perm, _ = Permission.objects.get_or_create(
            codename="add_testlistinstance", content_type=ct, defaults={"name": "Can add test list instance"}
        )
        self.group.permissions.add(perm)
        self.fill_testlist()
        inputs = self.wait_for_elements(By.CLASS_NAME, "qa-input", minimum=2)[:3]

        assert int(float(inputs[2].get_attribute("value"))) == 5
        assert models.TestListInstance.objects.count() == 0
        self.click("submit-qa")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        self.wait.until(lambda d: d.execute_script("return typeof jQuery !== 'undefined' ? jQuery.active == 0 : true"))

        assert models.TestListInstance.objects.count() == 1
        assert models.TestListInstance.objects.latest("pk").include_for_scheduling

        assert models.TestInstance.objects.filter(unit_test_info__test__type="simple")[0].value == 1
        assert models.TestInstance.objects.filter(unit_test_info__test__type="simple")[1].value == 2
        assert models.TestInstance.objects.get(unit_test_info__test__type="composite").value == 5
        now = timezone.now()
        date = timezone.localtime(now).date()
        assert models.TestInstance.objects.get(unit_test_info__test__type="date").date_value == date
        dt = timezone.localtime(now).replace(hour=12, minute=0, second=0, microsecond=0)
        assert models.TestInstance.objects.get(unit_test_info__test__type="datetime").datetime_value == dt
        assert models.TestInstance.objects.get(unit_test_info__test__type="string").string_value == "test"
        assert models.TestInstance.objects.get(unit_test_info__test__type="scomposite").string_value == "testchoiceb"
        assert models.TestInstance.objects.get(unit_test_info__test__type="multchoice").string_value == "choiceb"

    def test_comment(self):
        """ tests present"""
        self.fill_testlist()
        self.wait_for_elements(By.CSS_SELECTOR, ".revealcomment")[0].click()
        self.send_keys("id_form-0-comment", "testticomment")
        self.wait_for_elements(By.CSS_SELECTOR, ".revealcomment")[0].click()

        self.click("submit-qa")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        assert models.TestInstance.objects.filter(comment="testticomment").count() == 1

    def test_set_in_progress(self):
        """ tests present"""
        self.fill_testlist()

        self.click("in-progress-container")
        self.click("submit-qa")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        assert models.TestListInstance.objects.in_progress().count() == 1

    def test_perform_and_review(self):
        """Ensure that we can go through a full perform->review cycle"""

        utils.create_status(name="reviewed", slug="reviewed", is_default=False, requires_review=False)
        self.fill_testlist()
        self.click("submit-qa")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))

        self.open("/qc/session/unreviewed/")
        self.wait_for_ajax()

        self.click_by_link_text("Review")
        self.select_by_text("bot-status-select", "reviewed")

        self.send_keys("id_comment", "testlistcomment")
        self.click("post-comment")
        self.wait_until(lambda: models.Comment.objects.count() == 1, "the comment to be saved")
        assert models.Comment.objects.count() == 1

        assert models.TestListInstance.objects.unreviewed().count() == 1
        self.click("submit-review")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        assert models.TestListInstance.objects.unreviewed().count() == 0

    def test_perform_qc_viewport_sizes(self):
        """Ensure the perform-QC page's controls stay reachable at a range of common desktop viewport sizes"""

        # A small, deliberately-varied matrix rather than only the
        # suite's default 1920x1080: 1366x768 is still one of the most
        # common single-monitor laptop resolutions, and 960x1080
        # represents someone working the perform-QC page in one half of
        # a 1920x1080 display tiled side-by-side with something else -
        # not hypothetical, and exactly the kind of real-world width
        # that a viewport override capped to the real window (see
        # SeleniumTests.set_viewport_size) has to render correctly
        # rather than silently overflow.
        profiles = [
            ('half_screen_side_by_side', 960, 1080),
            ('small_laptop', 1366, 768),
            ('full_hd', 1920, 1080),
        ]

        for label, width, height in profiles:
            with self.subTest(profile=label, width=width, height=height):
                self.set_viewport_size(width, height)
                self.fill_testlist()

                inputs = self.wait_for_elements(By.CLASS_NAME, "qa-input", minimum=2)[:3]
                assert int(float(inputs[2].get_attribute("value"))) == 5

                submit = self.driver.find_element(By.ID, "submit-qa")
                assert submit.is_displayed()
                rect = self.driver.execute_script(
                    "var r = arguments[0].getBoundingClientRect();"
                    "return {left: r.left, right: r.right, vw: window.innerWidth};",
                    submit,
                )
                assert 0 <= rect['left'] and rect['right'] <= rect['vw'], (
                    "submit-qa rendered outside the %sx%s viewport (profile=%s): %s"
                    % (width, height, label, rect)
                )
                # Confirm it's not just present in the DOM within bounds,
                # but genuinely clickable there too - the earlier
                # tiling-WM bug left content geometrically "inside" the
                # viewport per getBoundingClientRect while still being
                # unclickable, because the *real* window was narrower
                # than the overridden logical one.
                submit.click()
                self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))

    def test_perform_and_initiate_se(self):
        """Ensure that we can go through a full perform->review cycle"""

        self.fill_testlist()
        self.click("init-se-container")
        self.click("submit-qa")

        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))

        # The date fields get their calendar from flatpickr, bound by
        # sl_serviceevent.js once the page's own JS has run. Focusing the
        # input before that binding exists just focuses a plain text box and
        # no calendar opens, so wait for the binding rather than guessing at
        # how long it takes - flatpickr records its instance on the element.
        self.wait.until(
            lambda d: d.execute_script(
                "var el = document.getElementById('id_datetime_service');"
                "return !!(el && el._flatpickr);"
            )
        )
        self.driver.execute_script("$('#id_datetime_service').focus()")

        # Wait for the calendar itself, not for wait_for_ajax(). jQuery.active
        # is a whole-page condition: any unrelated request still in flight on
        # this form keeps it above zero, so the test could sit here for the
        # full timeout with the calendar open and ready in front of it. That
        # is what the failure screenshots showed. What the click below needs
        # is the calendar, so wait for exactly that.
        self.wait.until(
            e_c.visibility_of_element_located((By.CSS_SELECTOR, ".flatpickr-calendar.open"))
        )
        self.click_by_css_selector(".today")
        self.wait_for_ajax()
        self.select_by_index("id_service_area_field_fake", 1)
        self.wait_for_ajax()
        self.select_by_index("id_service_type", 1)
        self.send_keys("id_problem_description", "Problem!")
        self.click("save-se")
        self.wait_for_ajax()
        assert models.TestListInstance.objects.first().serviceevents_initiated.count() == 1

    def test_autosave(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        self.login()
        self.open(self.url)
        # No sleep needed before wait_for_elements - waiting is what it does.
        inputs = self.wait_for_elements(By.CLASS_NAME, "qa-input", minimum=2)[:3]
        inputs[0].send_keys(1)
        assert models.AutoSave.objects.count() == 0
        # Kept: this paces the simulated typing so the debounce timer starts
        # from the first keystroke before Enter is sent. It is not waiting on
        # an observable condition, so there is nothing to wait on instead -
        # removing it makes the autosave never fire and the poll below time
        # out.
        time.sleep(1)
        inputs[0].send_keys(Keys.ENTER)
        # Autosave is debounced on a 4s interval. This used to sleep a flat
        # 4.2s and then assert; polling instead returns as soon as the row
        # lands, and still tolerates a slow run rather than failing at 4.2s.
        self.wait_until(
            lambda: models.AutoSave.objects.count() == 1,
            "the debounced autosave to be written",
            timeout=max(self.timeout, 10),
        )
        assert models.AutoSave.objects.count() == 1

    def test_load_autosave(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        tl2 = utils.create_test_list(name="day 2")
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

        url = reverse("perform_qa", kwargs={'pk': utc.pk})
        self.open(url + "?autosave_id=%d&day=%d" % (auto.pk, auto.day + 1))
        self.wait_for_ajax()

        inputs = self.wait_for_elements(By.CLASS_NAME, "qa-input", minimum=2)[:3]
        title = "Perform %s : day 2" % utc.unit.name
        # wait_for_elements, not find_elements: with the implicit wait off,
        # find_elements returns whatever has rendered so far, which on a
        # still-settling page can be an empty list.
        assert title in [el.text for el in self.wait_for_elements(By.CLASS_NAME, "box-title")]

        # The autosaved values arrive after the inputs do. wait_for_elements
        # waits for the elements to *exist*; nothing so far has waited for
        # them to be *filled in*, so reading .value here raced the restore and
        # got "" - which surfaces as "could not convert string to float: ''",
        # a failure that says nothing about what actually went wrong.
        self.wait.until(lambda d: inputs[0].get_attribute("value") != "")
        assert float(inputs[0].get_attribute("value")) == 1
        # id_work_started/id_work_completed are populated here via flatpickr's
        # setDate(), which always redisplays using FLATPICKR_DATETIME_FMT
        # ('Y-m-d H:i', changed from the human-readable 'd M Y H:i' in #832
        # for French-locale support) - not the "%d %b %Y %H:%M" human format
        # used for a freshly-rendered (non-autosave) initial value.
        # Derived, not hard-coded: flatpickr redisplays using the configured
        # datetime format, so a literal here would encode today's setting and
        # break the next time it changes - which is what happened in #832.
        started = date_format(timezone.datetime(1980, 5, 12, 12, 0), get_format('DATETIME_FORMAT'))
        completed = date_format(timezone.datetime(1980, 5, 12, 12, 1), get_format('DATETIME_FORMAT'))
        assert self.driver.find_element(By.ID, "id_work_started").get_attribute("value") == started
        assert self.driver.find_element(By.ID, "id_work_completed").get_attribute("value") == completed
        assert self.driver.find_element(By.ID, "id_work_duration").get_attribute("value") == "0hr:01min"
        assert self.driver.find_element(By.ID, "id_form-0-comment").get_attribute("value") == "test comment"
        assert self.driver.find_element(By.ID, "id_comment").get_attribute("value") == "test list instance comment"

    def test_submit_autosave(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""

        tl2 = utils.create_test_list(name="day 2")
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

        url = reverse("perform_qa", kwargs={'pk': utc.pk})
        self.open(url + "?autosave_id=%d&day=%d" % (auto.pk, auto.day + 1))
        self.wait_for_ajax()

        self.click("submit-qa")
        # click() returns as soon as the click is dispatched, not when the
        # POST it triggers has been handled - so without this the assertion
        # below raced the submission. It failed roughly two runs in three on
        # Chromium, and the failure screenshot showed the submit button still
        # reading "Submitting...". Every other submit-qa test in this file
        # already waits for the success alert; this one was the exception.
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))

        assert models.AutoSave.objects.filter(pk=auto.pk).count() == 0

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_perform_boolean(self):
        """Fill and submit a BOOLEAN-type test - models.BOOLEAN is never
        exercised through the browser anywhere in this suite (setUp's
        all_tests list wires up SIMPLE/COMPOSITE/DATE/DATETIME/
        MULTIPLE_CHOICE/STRING/STRING_COMPOSITE, but not BOOLEAN)."""
        raise NotImplementedError

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_perform_upload(self):
        """Fill and submit an UPLOAD-type test via a real file input -
        models.UPLOAD is never exercised through the browser anywhere in
        this suite, despite qa.js's load_autosave() having dedicated
        upload-handling logic (ti.set_value({'attachment_id': ...})) that
        nothing currently tests."""
        raise NotImplementedError

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_autosave_datetime_roundtrip(self):
        """Type a date into id_work_started via the UI, let it autosave,
        then assert the AutoSave.work_started value saved to the DB is
        what was actually intended. test_load_autosave (fixed on this
        branch) checks the *read* side of this same datetime-format bug
        class - autosave_load()'s response correctly reaching the
        rendered field - but nothing checks the *write* side: does typing
        a date into the flatpickr-driven field and letting autosave() run
        actually save the intended datetime, given the same
        DATETIME_INPUT_FORMATS-index confusion that caused the read-side
        bug could just as easily exist on this side too."""
        raise NotImplementedError


@pytest.mark.selenium
class TestReviewQC(BaseQATests):

    def setUp(self):
        with transaction.atomic():
            super().setUp()

            self.unreviewed = utils.create_status(name="Unreviewed", slug="unreviewed")
            self.reviewed = utils.create_status(name="Approved", slug="approved", is_default=False, requires_review=False)
            utils.create_test_instance()

            self.url = "/qc/session/unreviewed/"

    @override_settings(REVIEW_BULK=True)
    def test_review_ok(self):
        """Ensure that no failed tests on load and 3 "NO TOL" tests present"""
        with transaction.atomic():
            self.login()
            self.open(self.url)
            self.wait_for_ajax()
            self.wait_for_elements(By.CLASS_NAME, "test-selected-toggle")[0].click()
            self.select_by_text("bulk-status", "Approved")
            self.click("submit-review")
            assert models.TestListInstance.objects.unreviewed().count() == 1

            self.click("confirm-update")
            self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
            assert models.TestListInstance.objects.unreviewed().count() == 0

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_review_reject(self):
        """Reject/fail a test list instance during review, rather than
        approving it - test_review_ok only exercises the approve path."""
        raise NotImplementedError

    @pytest.mark.skip(reason="stub - not yet implemented")
    @override_settings(REVIEW_BULK=False)
    def test_review_non_bulk(self):
        """Review a test list instance with REVIEW_BULK=False - the only
        existing test in this class is decorated
        @override_settings(REVIEW_BULK=True), so the non-bulk review UI
        path has no coverage at all."""
        raise NotImplementedError

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_unreview(self):
        """Move an already-approved test list instance back to
        unreviewed. Every existing test in this class only exercises
        unreviewed -> reviewed; the reverse direction is untested."""
        raise NotImplementedError
