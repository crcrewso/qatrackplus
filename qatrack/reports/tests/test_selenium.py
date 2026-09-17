
import pytest
from django.urls import reverse
from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as e_c

from qatrack.qa.tests.test_selenium import BaseQATests
from qatrack.reports import models, qc


class TestReportInterface(BaseQATests):
    """Selenium coverage for the report builder page (/reports/).

    Moved out of qatrack/reports/tests/test_base.py, which mixed it in
    among ~20 unrelated non-Selenium test classes - the only Selenium
    tests in the codebase not already living in a dedicated
    test_selenium.py alongside their app's other tests (see
    qa/tests/test_selenium.py, service_log/tests/test_selenium.py,
    faults/tests/test_selenium.py).
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

    def test_save_report(self):
        """Ensure filling and saving a report results in a SavedReport in the db"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_work_completed')))
        assert models.SavedReport.objects.count() == 0
        self.click("save")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        assert models.SavedReport.objects.count() == 1
        sr = models.SavedReport.objects.first()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))

    def test_save_report_with_note(self):
        """Ensure adding notes to saved reports works"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_work_completed')))
        self.click("add-note")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_reportnote_set-0-heading')))
        self.send_keys("id_reportnote_set-0-heading", "heading")
        self.send_keys("id_reportnote_set-0-content", "content")

        assert models.ReportNote.objects.count() == 0
        self.click("save")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        expected_notes = [{"heading": "heading", "content": "content"}]
        assert list(models.ReportNote.objects.values("heading", "content")) == expected_notes

    def test_save_report_with_note_repeated_saves(self):
        """Ensure repeated saves only create one note"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_work_completed')))
        self.click("add-note")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_reportnote_set-0-heading')))
        self.send_keys("id_reportnote_set-0-heading", "heading")
        self.send_keys("id_reportnote_set-0-content", "content")

        assert models.ReportNote.objects.count() == 0
        for i in range(3):
            self.click("save")
            self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        expected_notes = [{"heading": "heading", "content": "content"}]
        assert list(models.ReportNote.objects.values("heading", "content")) == expected_notes

    def test_load_report(self):
        """Select report from table and make sure it loads"""

        sr = models.SavedReport.objects.create(
            report_type=qc.TestListInstanceSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        models.ReportNote.objects.create(
            report=sr,
            heading="heading",
            content="content",
        )

        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))
        self.click('report-id-%s' % sr.pk)
        wc = self.driver.find_element(By.ID, 'id_work_completed')
        assert wc.get_attribute("value") == "02 Jan 1989 - 04 Jan 1990"
        heading = self.driver.find_element(By.ID, "id_reportnote_set-0-heading")
        assert heading.get_attribute("value") == "heading"
        content = self.driver.find_element(By.ID, "id_reportnote_set-0-content")
        assert content.get_attribute("value") == "content"

    def test_load_report_edit_note(self):
        """Select report from table, edit its note and resave it"""

        sr = models.SavedReport.objects.create(
            report_type=qc.TestListInstanceSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        models.ReportNote.objects.create(
            report=sr,
            heading="heading",
            content="content",
        )

        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))
        self.click('report-id-%s' % sr.pk)
        heading = self.driver.find_element(By.ID, "id_reportnote_set-0-heading")
        heading.send_keys(" add some new text")
        self.click("save")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        expected_notes = [{"heading": "heading add some new text", "content": "content"}]
        assert list(models.ReportNote.objects.values("heading", "content")) == expected_notes

    def test_load_report_delete_note(self):
        """Select report from table, delete a note and then save it """

        sr = models.SavedReport.objects.create(
            report_type=qc.TestListInstanceSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        models.ReportNote.objects.create(
            report=sr,
            heading="heading",
            content="content",
        )

        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))
        self.click('report-id-%s' % sr.pk)
        self.click("id_reportnote_set-remove-0")
        self.click("save")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        assert models.ReportNote.objects.count() == 0

    def test_load_report_add_new_note_delete_old_note(self):
        """Ensure we can both add and delete notes in a single save"""

        sr = models.SavedReport.objects.create(
            report_type=qc.TestListInstanceSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        models.ReportNote.objects.create(
            report=sr,
            heading="heading",
            content="content",
        )

        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))
        self.click('report-id-%s' % sr.pk)
        self.click("add-note")
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_reportnote_set-1-heading')))
        self.send_keys("id_reportnote_set-1-heading", "heading new")
        self.send_keys("id_reportnote_set-1-content", "content new")
        self.click("id_reportnote_set-remove-0")
        self.click("save")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        expected_notes = [{"heading": "heading new", "content": "content new"}]
        assert list(models.ReportNote.objects.values("heading", "content")) == expected_notes

    def test_schedule_report(self):
        """Ensure scheduling a savedreport works"""

        sr = models.SavedReport.objects.create(
            report_type=qc.TestListInstanceSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        # need to reload page to get report table
        self.driver.refresh()

        self.click('report-id-%s' % sr.pk)

        self.click('report-id-%s-schedule' % sr.pk)

        self.select_by_index('id_schedule-time', 1)
        self.driver.find_element(By.ID, "id_schedule-emails").send_keys("a@b.com")

        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'add-date')))
        self.driver.find_element(By.CLASS_NAME, "add-date").click()

        self.click("schedule")

        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        sched = str(models.ReportSchedule.objects.first().schedule)
        assert timezone.localtime(timezone.now()).strftime("%Y%m%d") in sched

    def test_clear_schedule(self):
        """Test clearing the schedule from a saved report"""

        sr = models.SavedReport.objects.create(
            report_type=qc.TestListInstanceSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        rec = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE"
        models.ReportSchedule.objects.create(
            report=sr,
            time="00:00:00",
            schedule=rec,
            created_by=self.user,
            modified_by=self.user,
        )

        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))

        self.click("report-id-%s-schedule" % sr.pk)
        self.wait_for_ajax()

        self.click("clear-schedule")
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        assert models.ReportSchedule.objects.count() == 0

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_delete_saved_report(self):
        """Delete a saved report entirely via the UI (reports-delete) -
        every existing test in this class that touches an existing
        SavedReport edits or schedules it; none delete it."""
        raise NotImplementedError
