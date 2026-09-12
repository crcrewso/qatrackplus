from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as e_c

from qatrack.qa.tests.test_selenium import BaseQATests
from qatrack.reports import qc


class TestReportInterface(BaseQATests):
    """Selenium coverage for the report builder page (/reports/).

    Moved out of qatrack/reports/tests/test_base.py, which mixes it in
    among ~20 unrelated non-Selenium test classes - the only Selenium
    tests in the codebase not already living in a dedicated
    test_selenium.py alongside their app's other tests (see
    qa/tests/test_selenium.py, service_log/tests/test_selenium.py,
    faults/tests/test_selenium.py). Only test_report_preview has been
    moved here so far; the rest of TestReportInterface's tests remain in
    test_base.py pending the same move.
    """

    def setUp(self):
        super().setUp()
        self.login()
        self.open(reverse("reports"))
        self.wait.until(e_c.presence_of_element_located((By.ID, 'select2-id_root-report_type-container')))

    def test_report_preview(self):
        """Select report and make sure it previews"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_work_completed')))
        self.click("preview")
        self.driver.find_element(By.CSS_SELECTOR, '#report .container-fluid')
