from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from qatrack.qatrack_core.utils import set_paper_size
from qatrack.reports.forms import ReportForm
from qatrack.reports.models import SavedReport


class TestPaperSizeCss(TestCase):
    """Chrome has no working paper size switch, so the size has to be set in
    CSS.  These assert against the real helper rather than a copy of it: the
    previous version of this module tested a local reimplementation of the
    command builder, so it kept passing while production silently emitted
    Letter for every report."""

    def setUp(self):
        self.html = "<html><head><style>p { color: red; }</style></head><body>Test</body></html>"

    def test_letter_rule_added(self):
        assert "@page { size: letter; }" in set_paper_size(self.html, "letter")

    def test_a4_rule_added(self):
        assert "@page { size: a4; }" in set_paper_size(self.html, "a4")

    def test_rule_goes_last_in_head(self):
        """It has to come after reports/pdf.css to win the cascade."""
        out = set_paper_size(self.html, "a4")
        assert out.index("p { color: red; }") < out.index("@page { size: a4; }") < out.index("</head>")

    def test_case_is_normalised(self):
        assert "@page { size: a4; }" in set_paper_size(self.html, "A4")

    def test_document_body_is_untouched(self):
        assert "<body>Test</body>" in set_paper_size(self.html, "a4")

    def test_fragment_without_head_still_gets_rule(self):
        out = set_paper_size("<p>fragment</p>", "a4")
        assert out.startswith("<style>@page { size: a4; }</style>")
        assert out.endswith("<p>fragment</p>")

    def test_only_first_head_is_targeted(self):
        out = set_paper_size("<html><head></head><body></head></body></html>", "letter")
        assert out.count("@page { size: letter; }") == 1


class TestPaperSizeDefaults(TestCase):
    """Test default paper size settings in models and forms."""

    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')

    def test_saved_report_default_paper_size(self):
        """Test that SavedReport defaults to letter paper size."""
        report = SavedReport.objects.create(
            title="Test Report",
            report_type="testlistinstance_summary",
            report_format="pdf",
            created_by=self.user,
            modified_by=self.user
        )
        self.assertEqual(report.paper_size, 'letter')

    def test_report_form_default_paper_size(self):
        """Test that ReportForm defaults to letter paper size."""
        form = ReportForm()
        self.assertEqual(form.fields['paper_size'].initial, 'letter')

    def test_report_form_paper_size_choices(self):
        """Test that form includes both paper size options."""
        form = ReportForm()
        choices = [choice[0] for choice in form.fields['paper_size'].choices]
        self.assertIn('letter', choices)
        self.assertIn('a4', choices)


class TestCleanPaperSize(TestCase):
    """The value is interpolated into a CSS declaration, so it is validated.

    An unexpected string does not fail loudly - it changes the rendered
    document - which is the wrong failure mode for a QC record.
    """

    def test_valid_sizes_pass_through_normalised(self):
        from qatrack.qatrack_core.utils import clean_paper_size

        assert clean_paper_size("letter") == "letter"
        assert clean_paper_size("A4") == "a4"
        assert clean_paper_size(" Letter ") == "letter"

    def test_empty_falls_back_to_letter(self):
        from qatrack.qatrack_core.utils import clean_paper_size

        assert clean_paper_size("") == "letter"
        assert clean_paper_size(None) == "letter"

    def test_unexpected_value_is_rejected(self):
        from qatrack.qatrack_core.utils import clean_paper_size

        with self.assertRaises(ValueError):
            clean_paper_size("legal")

    def test_css_injection_is_rejected(self):
        from qatrack.qatrack_core.utils import clean_paper_size

        with self.assertRaises(ValueError):
            clean_paper_size("letter; } body { display: none } @page {")


class TestBothEnginesShareOnePaperSizeMechanism(TestCase):
    """Chrome and WeasyPrint must not set page geometry different ways.

    Margins live in reports/pdf.css and the size is injected by
    set_paper_size(), which both engines call. Previously WeasyPrint passed
    its own stylesheet declaring both, so the margin was stated twice and had
    to be kept in step with pdf.css by hand.
    """

    def test_weasyprint_renders_a_pdf(self):
        from qatrack.qatrack_core.utils import weasyprint_to_pdf

        pdf = weasyprint_to_pdf("<html><body><h1>hi</h1></body></html>")
        assert pdf[:4] == b"%PDF", pdf[:20]

    def test_weasyprint_honours_the_injected_size(self):
        from qatrack.qatrack_core.utils import weasyprint_to_pdf

        html = "<html><head></head><body><h1>hi</h1></body></html>"
        assert weasyprint_to_pdf(html, paper_size="letter") != weasyprint_to_pdf(html, paper_size="a4")

    def test_weasyprint_adds_no_margin_rule_of_its_own(self):
        """pdf.css is the only place margins are declared."""
        import inspect

        from qatrack.qatrack_core import utils

        assert "margin:" not in inspect.getsource(utils.weasyprint_to_pdf)


class TestChromeFailureReporting(TestCase):
    """A failed report should say which thing failed.

    Neither the exit status nor the output file was checked, so a browser that
    ran and produced nothing surfaced as "executable not found" - naming the
    one component that was working. See #835, where the reporter had a browser
    that ran the command by hand but silently failed under the service.
    """

    def test_missing_chrome_path_names_the_setting(self):
        from qatrack.qatrack_core.utils import ChromeNotFound, chrometopdf

        with override_settings(CHROME_PATH=""):
            with self.assertRaises(ChromeNotFound) as caught:
                chrometopdf("<html><body>x</body></html>")
        assert "CHROME_PATH" in str(caught.exception)

    def test_unrunnable_executable_is_reported_as_not_found(self):
        from qatrack.qatrack_core.utils import ChromeNotFound, chrometopdf

        with override_settings(CHROME_PATH="/nonexistent/browser"):
            with self.assertRaises(ChromeNotFound):
                chrometopdf("<html><body>x</body></html>")

    def test_a_browser_that_produces_no_pdf_is_not_reported_as_missing(self):
        """The #835 case: it runs, it exits, there is no PDF."""
        from qatrack.qatrack_core.utils import ChromeNotFound, ChromePdfFailed, chrometopdf

        with override_settings(CHROME_PATH="/bin/true"):
            with self.assertRaises(ChromePdfFailed) as caught:
                chrometopdf("<html><body>x</body></html>")
        assert not isinstance(caught.exception, ChromeNotFound)
        assert "wrote no PDF" in str(caught.exception)

    def test_nonzero_exit_is_reported_with_the_log_location(self):
        from qatrack.qatrack_core.utils import ChromePdfFailed, chrometopdf

        with override_settings(CHROME_PATH="/bin/false"):
            with self.assertRaises(ChromePdfFailed) as caught:
                chrometopdf("<html><body>x</body></html>")
        assert "report-stderr.txt" in str(caught.exception)


class TestEngineSelection(TestCase):
    """Which engine renders a report is a decision, not an accident.

    It used to be made by exception - try WeasyPrint, fall back to Chrome on
    anything at all - so a WeasyPrint failure produced a differently rendered
    report instead of an error, and on a host with no browser it produced
    Chrome's error instead of WeasyPrint's.
    """

    def test_auto_prefers_chrome_when_available(self):
        from unittest import mock

        from qatrack.qatrack_core import utils

        with override_settings(PDF_ENGINE="auto"):
            with mock.patch.object(utils, "chrome_available", return_value=True), \
                 mock.patch.object(utils, "chrometopdf", return_value=b"%PDF-chrome") as chrome:
                assert utils.html_to_pdf("<html></html>") == b"%PDF-chrome"
        assert chrome.called

    def test_auto_falls_back_to_weasyprint_without_chrome(self):
        from unittest import mock

        from qatrack.qatrack_core import utils

        with override_settings(PDF_ENGINE="auto"):
            with mock.patch.object(utils, "chrome_available", return_value=False), \
                 mock.patch.object(utils, "weasyprint_available", return_value=True), \
                 mock.patch.object(utils, "weasyprint_to_pdf", return_value=b"%PDF-wp") as wp:
                assert utils.html_to_pdf("<html></html>") == b"%PDF-wp"
        assert wp.called

    def test_neither_engine_is_an_error_not_a_silent_failure(self):
        from unittest import mock

        from qatrack.qatrack_core import utils

        with override_settings(PDF_ENGINE="auto"):
            with mock.patch.object(utils, "chrome_available", return_value=False), \
                 mock.patch.object(utils, "weasyprint_available", return_value=False):
                with self.assertRaises(utils.PdfGenerationError) as caught:
                    utils.html_to_pdf("<html></html>")
        assert "CHROME_PATH" in str(caught.exception)

    def test_weasyprint_can_be_pinned(self):
        """The #835 case: a site that cannot install a browser."""
        from unittest import mock

        from qatrack.qatrack_core import utils

        with override_settings(PDF_ENGINE="weasyprint"):
            with mock.patch.object(utils, "chrome_available", return_value=True), \
                 mock.patch.object(utils, "weasyprint_to_pdf", return_value=b"%PDF-wp") as wp:
                assert utils.html_to_pdf("<html></html>") == b"%PDF-wp"
        assert wp.called

    def test_chrome_can_be_pinned(self):
        from unittest import mock

        from qatrack.qatrack_core import utils

        with override_settings(PDF_ENGINE="chrome"):
            with mock.patch.object(utils, "chrometopdf", return_value=b"%PDF-chrome") as chrome:
                assert utils.html_to_pdf("<html></html>") == b"%PDF-chrome"
        assert chrome.called

    def test_unknown_engine_is_rejected(self):
        from qatrack.qatrack_core import utils

        with override_settings(PDF_ENGINE="prince"):
            with self.assertRaises(utils.PdfGenerationError) as caught:
                utils.html_to_pdf("<html></html>")
        assert "prince" in str(caught.exception)

    def test_real_report_still_renders_end_to_end(self):
        from qatrack.reports import reports

        assert reports.BaseReport(report_opts={}).to_pdf()[:4] == b"%PDF"
