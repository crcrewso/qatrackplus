"""A Django comment that spans lines is not a comment - it is printed.

``{# ... #}`` is documented as single-line only: "the comment delimiters cannot
be separated by newlines". Give it a newline and the template engine does not
recognise it at all, so the whole thing survives into the HTML as a text node.
Nothing warns, no test of the rendered classes notices, and the page still has
every element it is supposed to have - the words are simply there, between the
rows, on every row.

That happened here. ``_form_horizontal.html`` gained a five-line ``{# #}``
explaining its clearfix, and every row the partial rendered carried the
explanation - on the fault forms, the QC perform page's fault form, the backup
form, three forms in the reports page and four more built in ``reports/views.py``,
and the service-event pages. The text also contains a literal ``<form
class="form">``, which a browser parses as a real start tag. crane measured it
on 2026-11-06 and sent the fix.

The scan below also found a second one, in ``admin/base_site.html``, which does
*not* print: it sits outside every block in a template that ``{% extends %}``,
and Django discards content in that position. It was one move away from printing,
and it is the same mistake, so it is now a block comment too.

Both tests are here because the two halves fail independently: the scan catches
the syntax anywhere in the tree, and the render catches the one partial whose
output is hardest to eyeball, since its comment appears once per field.
"""

import pathlib
import re

from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase

QATRACK = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = QATRACK.parent

OPEN = re.compile(r"\{#")


def template_files():
    """Every template in the project, excluding anything vendored or built."""
    skip = (".venv", "node_modules", "_build", "site-packages", "static/vendor")
    return sorted(
        p for p in REPO_ROOT.rglob("*.html")
        if not any(part in str(p) for part in skip)
    )


def comments_that_span_lines(text):
    """Offsets of every `{#` whose `#}` is not on the same line."""
    found = []
    for match in OPEN.finditer(text):
        rest = text[match.end():]
        close = rest.find("#}")
        newline = rest.find("\n")
        if close == -1 or (newline != -1 and newline < close):
            found.append((text[:match.start()].count("\n") + 1, rest.split("\n")[0][:70]))
    return found


class TestNoTemplateCommentSpansLines:

    def test_there_are_templates_to_check(self):
        """Guard against the glob quietly matching nothing."""
        files = template_files()
        assert len(files) > 100, "only %d templates found under %s" % (len(files), REPO_ROOT)

    def test_no_template_uses_the_single_line_form_across_lines(self):
        offenders = []
        for path in template_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for line, excerpt in comments_that_span_lines(text):
                offenders.append(
                    "%s:%d  {#%s" % (path.relative_to(REPO_ROOT), line, excerpt)
                )
        assert not offenders, (
            "`{# #}` cannot span lines - Django prints the whole thing into the "
            "HTML. Use {%% comment %%}...{%% endcomment %%} instead:\n  %s"
            % "\n  ".join(offenders)
        )


class FourFieldForm(forms.Form):
    """Four fields, because the comment was inside the per-field loop.

    Rendering the partial with no form at all renders nothing: the loop body
    never runs, so the comment never gets the chance to print. A test that does
    that passes whatever the template says, which is how the first version of
    this file managed to be green against the broken template.
    """

    one = forms.CharField()
    two = forms.CharField()
    three = forms.CharField()
    four = forms.CharField()


class TestTheFormPartialsRenderNoComment(SimpleTestCase):
    """The ones that were actually printing, checked through the engine.

    The scan above catches the syntax returning. This catches the output, which
    is what a user would have seen, and does not care how the comment is
    written. Both partials are checked: either could grow one.
    """

    PARTIALS = ("_form.html", "_form_horizontal.html")

    def rendered(self, partial):
        return render_to_string(partial, {"form": FourFieldForm()})

    def test_the_render_actually_produces_rows(self):
        """Without this, every assertion below passes on an empty string."""
        for partial in self.PARTIALS:
            html = self.rendered(partial)
            assert html.count("form-group") >= 4, (
                "%s rendered %d rows, so the checks below prove nothing"
                % (partial, html.count("form-group"))
            )

    def test_no_comment_delimiter_survives(self):
        for partial in self.PARTIALS:
            html = self.rendered(partial)
            assert "{#" not in html and "#}" not in html, (
                "%s leaves a comment delimiter in the rendered HTML" % partial
            )

    def test_the_clearfix_explanation_is_not_on_the_page(self):
        """Named rather than generic: this is the text that was being printed."""
        for partial in self.PARTIALS:
            html = self.rendered(partial)
            for phrase in ("col-sm-* children float", "form-horizontal .form-group"):
                assert phrase not in html, (
                    "%r is being printed into the page by %s" % (phrase, partial)
                )
