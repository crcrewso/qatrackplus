"""
test_browser.py
~~~~~~~~~~~~~~~

Playwright browser tests for the Reports module.

Migrated from the Selenium-based ``test_base.py``.  The ``TestReportInterface``
class is marked with ``@pytest.mark.browser`` and relies on the
``PlaywrightTests`` base class via ``BaseQATests`` from
``qatrack.qa.tests.test_browser``.
"""
import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from qatrack.qa.tests.test_browser import BaseQATests
from qatrack.reports import models, qc


@pytest.mark.browser
class TestReportInterface(BaseQATests):

    def setUp(self):
        super().setUp()
        self.login()
        self.open(reverse("reports"))
        self.page.locator('#select2-id_root-report_type-container').wait_for()

    def test_report_preview(self):
        """Select report and make sure it previews"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.page.locator('#id_work_completed').wait_for()
        self.click("preview")
        expect(self.page.locator('#report .container-fluid')).to_be_visible()

    def test_save_report(self):
        """Ensure filling and saving a report results in a SavedReport in the db"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.page.locator('#id_work_completed').wait_for()
        assert models.SavedReport.objects.count() == 0
        self.click("save")
        self.page.locator('.success-message').wait_for()
        assert models.SavedReport.objects.count() == 1
        sr = models.SavedReport.objects.first()
        self.page.locator(f'#report-id-{sr.pk}').wait_for()

    def test_save_report_with_note(self):
        """Ensure adding notes to saved reports works"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.page.locator('#id_work_completed').wait_for()
        self.click("add-note")
        self.page.locator('#id_reportnote_set-0-heading').wait_for()
        self.send_keys("id_reportnote_set-0-heading", "heading")
        self.send_keys("id_reportnote_set-0-content", "content")

        assert models.ReportNote.objects.count() == 0
        self.click("save")
        self.page.locator('.success-message').wait_for()
        expected_notes = [{"heading": "heading", "content": "content"}]
        assert list(models.ReportNote.objects.values("heading", "content")) == expected_notes

    def test_save_report_with_note_repeated_saves(self):
        """Ensure repeated saves only create one note"""
        self.select_by_text('id_root-report_type', qc.TestListInstanceSummaryReport.name)
        self.page.locator('#id_work_completed').wait_for()
        self.click("add-note")
        self.page.locator('#id_reportnote_set-0-heading').wait_for()
        self.send_keys("id_reportnote_set-0-heading", "heading")
        self.send_keys("id_reportnote_set-0-content", "content")

        assert models.ReportNote.objects.count() == 0
        for _ in range(3):
            self.click("save")
            self.page.locator('.success-message').wait_for()
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

        # Reload page to pick up the newly created report in the table.
        self.page.reload()
        self.page.locator(f'#report-id-{sr.pk}').wait_for()
        self.click(f'report-id-{sr.pk}')
        expect(self.page.locator('#id_work_completed')).to_have_value("02 Jan 1989 - 04 Jan 1990")
        expect(self.page.locator('#id_reportnote_set-0-heading')).to_have_value("heading")
        expect(self.page.locator('#id_reportnote_set-0-content')).to_have_value("content")

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

        # Reload page to pick up the newly created report in the table.
        self.page.reload()
        self.page.locator(f'#report-id-{sr.pk}').wait_for()
        self.click(f'report-id-{sr.pk}')
        # Append text to the existing heading value.
        heading_loc = self.page.locator('#id_reportnote_set-0-heading')
        expect(heading_loc).to_have_value("heading")
        heading_loc.fill("heading add some new text")
        self.click("save")
        self.page.locator('.success-message').wait_for()
        expected_notes = [{"heading": "heading add some new text", "content": "content"}]
        assert list(models.ReportNote.objects.values("heading", "content")) == expected_notes

    def test_load_report_delete_note(self):
        """Select report from table, delete a note and then save it"""
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

        # Reload page to pick up the newly created report in the table.
        self.page.reload()
        self.page.locator(f'#report-id-{sr.pk}').wait_for()
        self.click(f'report-id-{sr.pk}')
        self.click("id_reportnote_set-remove-0")
        self.click("save")
        self.page.locator('.success-message').wait_for()
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

        # Reload page to pick up the newly created report in the table.
        self.page.reload()
        self.page.locator(f'#report-id-{sr.pk}').wait_for()
        self.click(f'report-id-{sr.pk}')
        self.click("add-note")
        self.page.locator('#id_reportnote_set-1-heading').wait_for()
        self.send_keys("id_reportnote_set-1-heading", "heading new")
        self.send_keys("id_reportnote_set-1-content", "content new")
        self.click("id_reportnote_set-remove-0")
        self.click("save")
        self.page.locator('.success-message').wait_for()
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
        # Reload page to pick up the newly created report in the table.
        self.page.reload()

        self.click(f'report-id-{sr.pk}')
        self.click(f'report-id-{sr.pk}-schedule')

        self.select_by_index('id_schedule-time', 1)
        self.send_keys("id_schedule-emails", "a@b.com")

        self.page.locator('.add-date').wait_for()
        self.page.locator('.add-date').click()

        self.click("schedule")

        self.page.locator('.alert-success').wait_for()
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

        # Reload page to pick up the newly created report in the table.
        self.page.reload()
        self.page.locator(f'#report-id-{sr.pk}').wait_for()

        self.click(f"report-id-{sr.pk}-schedule")
        self.page.locator('#clear-schedule').wait_for()

        self.click("clear-schedule")
        self.page.locator('.alert-success').wait_for()
        assert models.ReportSchedule.objects.count() == 0
