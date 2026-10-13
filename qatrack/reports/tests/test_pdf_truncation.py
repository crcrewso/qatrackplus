"""Guards against the silent report truncation that v4 shipped.

v4 moved PDF rendering from Chrome to WeasyPrint, after which report downloads
were cut off after the first few pages, because WeasyPrint could fragment
neither a flex container nor a float across pages and Bootstrap floats every
grid column. The on-screen preview never loads the print stylesheet, so the
reports looked right and arrived incomplete - for a QC record, the worst
failure mode there is.

**Measured on WeasyPrint 65.1, which is not what v4 shipped against:**

    .row              .col-xs-12      pages   content after the break
    display: flex     float: left     6       kept
    display: flex     float: none     6       kept
    display: block    float: left     1       DROPPED
    display: block    float: none     6       kept

So the flex half is fixed upstream and the **float half is not**. That matters
for which rule in `reports/pdf.css` is load-bearing: `.row { display: block }`
is what *activates* the float, and `.col-xs-12 { float: none }` is what then
keeps the document fragmentable. Remove only the second and the truncation
returns. The two are a pair.

Three levels of guard, because each catches what the others cannot:

* the **cause** - the stylesheet rules themselves. Needs no engine, so it runs
  on CI without a browser or Pango.
* the **instrument** - that pypdf can actually tell a truncated render from a
  complete one on this install. Without it a broken reader would make every
  check below pass silently.
* the **symptom** - a real multi-page render per engine, the only thing that
  would catch a *new* cause of the same failure.
"""

import io
import re

from django.template.loader import get_template
from django.test import TestCase, override_settings

from qatrack.qatrack_core.utils import chrome_available, html_to_pdf, weasyprint_available

MARKER = "TRAILINGCONTENTSENTINEL"

#: Long enough to need several pages whichever engine renders it.
FILLER = "<p>%s</p>" % (("Measured value and tolerance. " * 30 + "<br>") * 20)

#: The break sits *inside* the grid container, which is how the report templates
#: are built and the only arrangement that truncates. A break *between* two rows
#: fragments fine, which is why a first draft of this test could not fail.
REPORT_HTML = """
<html><head><style>%%s</style></head><body>
  <div class="row"><div class="col-xs-12">
    <h1>First</h1>%(filler)s
    <div style="page-break-before: always"></div>
    <h1>Second</h1><p>%(marker)s</p>
  </div></div>
</body></html>
""" % {"filler": FILLER, "marker": MARKER}

#: Bootstrap's grid as the browser sees it, reduced to the declaration that
#: still breaks fragmentation on WeasyPrint 65.1.
TRUNCATING_CSS = ".row { display: block; } .col-xs-12 { float: left; width: 100%; }"

#: What reports/pdf.css does about it.
FIXED_CSS = ".row { display: block; } .col-xs-12 { float: none; width: 100%; }"


def read_pdf(data):
    """Page count and text, read back from rendered bytes with pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "".join(page.extract_text() or "" for page in reader.pages)
    return len(reader.pages), re.sub(r"\s+", "", text)


class TestPrintStylesheetKeepsContentFragmentable(TestCase):
    """The cause guard: the pair of rules whose absence truncated long reports."""

    def setUp(self):
        self.css = re.sub(r"/\*.*?\*/", "", get_template("reports/pdf.css").template.source, flags=re.S)

    def _blocks(self, selector):
        return [
            m.group(1)
            for m in re.finditer(r"(?:^|[,{}\s])%s\s*\{([^}]*)\}" % re.escape(selector), self.css, re.M)
        ]

    def test_full_width_columns_do_not_float_in_print(self):
        """The load-bearing one on current WeasyPrint."""
        blocks = self._blocks(".col-xs-12")
        assert blocks, "reports/pdf.css no longer styles .col-xs-12 - the fix has been removed"
        assert any(re.search(r"float\s*:\s*none", b) for b in blocks), (
            "reports/pdf.css must keep `.col-xs-12 { float: none }`. A float cannot be "
            "fragmented across pages, Bootstrap floats every grid column, and `.row { "
            "display: block }` below makes that float active - so without this rule a "
            "report with a forced page break silently loses everything after it."
        )

    def test_row_is_not_a_flex_container_in_print(self):
        """Belt and braces now, but keep it: it is one half of a pair."""
        blocks = self._blocks(".row")
        assert blocks, "reports/pdf.css no longer styles .row - the fix has been removed"
        assert not any(re.search(r"display\s*:\s*flex", b) for b in blocks), (
            ".row is flex again in the print stylesheet. WeasyPrint 65.1 fragments flex "
            "correctly, so this is no longer fatal on its own - but it was in v4, and "
            "the supported WeasyPrint range is wider than one version."
        )


class TestPypdfCanDetectTruncation(TestCase):
    """The instrument check: can this install's pypdf see a truncated render at all?

    Every other assertion here is only as good as the reader. If `extract_text`
    returned "" on this platform, or pypdf mis-counted pages, the symptom tests
    would pass on a truncated document and report success. So prove the
    discrimination directly, on known-good and known-bad input, rather than
    assuming it.
    """

    def setUp(self):
        if not weasyprint_available():
            self.skipTest("WeasyPrint cannot load on this host")

    def render(self, css):
        with override_settings(PDF_ENGINE="weasyprint"):
            return html_to_pdf(REPORT_HTML % css, paper_size="letter")

    def test_pypdf_reads_back_a_complete_render(self):
        pages, text = read_pdf(self.render(FIXED_CSS))
        assert pages >= 2, "expected a multi-page document, pypdf reports %d page(s)" % pages
        assert MARKER in text, (
            "pypdf could not find the trailing content in a document that does contain "
            "it - the reader or its text extraction is not usable for these guards"
        )

    def test_pypdf_sees_content_missing_from_a_truncated_render(self):
        """The negative half. Bootstrap's floated grid still truncates on 65.1."""
        pages, text = read_pdf(self.render(TRUNCATING_CSS))
        assert MARKER not in text, (
            "a floated full-width column no longer truncates on this WeasyPrint "
            "(%d page(s)). That is good news upstream, but it means this instrument "
            "check no longer proves pypdf can detect truncation - find another known-bad "
            "input before trusting the guards above." % pages
        )


class EngineTruncationMixin:
    """Render a multi-page report through one engine and insist all of it arrives."""

    engine = None

    def test_a_forced_page_break_does_not_lose_what_follows_it(self):
        with override_settings(PDF_ENGINE=self.engine):
            data = html_to_pdf(REPORT_HTML % FIXED_CSS, paper_size="letter")
        pages, text = read_pdf(data)
        assert pages >= 2, "a forced page break should give at least two pages, got %d" % pages
        assert MARKER in text, (
            "%s lost the content after the forced page break, across %d page(s) - this is "
            "the v4 silent truncation returning by some new route" % (self.engine, pages)
        )


class TestWeasyPrintDoesNotTruncate(EngineTruncationMixin, TestCase):
    engine = "weasyprint"

    def setUp(self):
        if not weasyprint_available():
            self.skipTest("WeasyPrint cannot load on this host")


class TestChromeDoesNotTruncate(EngineTruncationMixin, TestCase):
    engine = "chrome"

    def setUp(self):
        if not chrome_available():
            self.skipTest("No Chrome/Chromium on this host")
