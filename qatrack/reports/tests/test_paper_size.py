from django.contrib.auth.models import User
from django.test import TestCase

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
