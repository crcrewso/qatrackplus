"""#818: form rows alternate background colour, so a long form reads as rows.

These tests pin the *mechanism* in both halves, because either half can be
right while the page looks unchanged:

- the templates have to emit alternating classes, and they have to **reset per
  form** - `{% cycle %}` keeps its state in the render context, so a page with
  two forms rendered through the same partial would carry the cycle across and
  the second form could start on the wrong parity. `forloop.counter` cannot do
  that, which is why it is used instead;
- the stylesheet has to give one of those classes a background. A class that no
  rule matches is the failure mode nobody notices, since the markup still looks
  correct in the page source.

The stylesheet is parsed with tinycss2, which arrives with WeasyPrint, the same
way `reports/tests/test_schedule_dialog_css.py` does it.
"""

import os
import pathlib
import re

import tinycss2
from django import forms
from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

PARTIALS = ('_form.html', '_form_horizontal.html')
BASE_CSS = os.path.join(
    settings.PROJECT_ROOT, 'qatrack_core', 'static', 'qatrack_core', 'css', 'base.css'
)


class FourFieldForm(forms.Form):
    one = forms.CharField()
    two = forms.CharField()
    three = forms.CharField()
    four = forms.CharField()


def rendered_row_classes_from(html):
    return re.findall(r'form-row-(odd|even)', html)


def rendered_row_classes(partial, form):
    return rendered_row_classes_from(render_to_string(partial, {'form': form}))


def read_template_source(name):
    from django.template.loader import get_template
    with open(get_template(name).origin.name, encoding='utf8') as f:
        return f.read()


class TestFormRowStriping(SimpleTestCase):

    def test_both_partials_alternate(self):
        for partial in PARTIALS:
            assert rendered_row_classes(partial, FourFieldForm()) == [
                'odd', 'even', 'odd', 'even'
            ], partial

    def test_a_second_form_on_the_page_starts_at_odd_again(self):
        """The parity resets per form, which `{% cycle %}` would not do."""
        for partial in PARTIALS:
            first = rendered_row_classes(partial, FourFieldForm())
            second = rendered_row_classes(partial, FourFieldForm())
            assert first == second, partial
            assert second[0] == 'odd', partial

    def test_an_errored_row_keeps_its_stripe(self):
        """`has-error` is rendered in the same class list; neither may displace
        the other."""
        form = FourFieldForm(data={'one': '', 'two': 'x', 'three': 'y', 'four': 'z'})
        assert not form.is_valid()
        for partial in PARTIALS:
            html = render_to_string(partial, {'form': form})
            assert 'has-error' in html, partial
            assert re.findall(r'form-row-(odd|even)', html) == ['odd', 'even', 'odd', 'even'], partial


class TestAFormCanOptOut(SimpleTestCase):
    """Striping is there to group a long form into rows. A form of two or three
    fields in a box of its own has nothing to group, and the tint just looks
    like one field is selected - so a template can turn it off."""

    def test_no_stripe_suppresses_the_classes_but_nothing_else(self):
        form = FourFieldForm()
        for partial in PARTIALS:
            html = render_to_string(partial, {'form': form, 'no_stripe': True})
            assert rendered_row_classes_from(html) == [], partial
            assert html.count('class="form-group') == 4, partial

    def test_the_default_is_still_striped(self):
        """Nothing that does not ask to opt out may lose its stripe."""
        for partial in PARTIALS:
            assert rendered_row_classes(partial, FourFieldForm()) == [
                'odd', 'even', 'odd', 'even'
            ], partial

    def test_an_opted_out_row_keeps_its_error_class(self):
        form = FourFieldForm(data={'one': '', 'two': 'x', 'three': 'y', 'four': 'z'})
        assert not form.is_valid()
        for partial in PARTIALS:
            html = render_to_string(partial, {'form': form, 'no_stripe': True})
            assert 'has-error' in html, partial
            assert rendered_row_classes_from(html) == [], partial


class TestTheLoginPageOptsOut(SimpleTestCase):
    """Two fields in a box of their own: the stripe groups nothing there, and
    reads as a selected field instead."""

    def test_the_login_template_passes_no_stripe(self):
        source = read_template_source('registration/login.html')
        include = re.search(r'\{%\s*include\s+"_form(?:_horizontal)?\.html"[^%]*%\}', source)
        assert include, 'login.html no longer includes a form partial'
        assert 'no_stripe=True' in include.group(0), (
            'login.html includes the form partial without opting out of striping: %r'
            % include.group(0)
        )


class TestTheHorizontalRowEnclosesItsColumns(SimpleTestCase):
    """The horizontal partial's row holds floated `col-sm-*` children, and
    Bootstrap clears them only for `.form-horizontal .form-group`. Two of this
    partial's callers do not provide that context, so without an explicit
    clearfix the row collapses to its padding height and the stripe does not
    cover the field it is meant to be behind."""

    def test_the_horizontal_row_is_clearfixed(self):
        html = render_to_string('_form_horizontal.html', {'form': FourFieldForm()})
        rows = re.findall(r'<div class="(form-group[^"]*)"', html)
        assert rows, 'the horizontal partial no longer renders form-group rows'
        for row in rows:
            assert 'clearfix' in row.split(), (
                'a horizontal row does not clear its floated columns: %r' % row
            )

    def test_bootstrap_does_not_clear_a_bare_form_group(self):
        """If this ever stops being true the clearfix above is redundant, and
        this test says so rather than leaving it unexplained."""
        bootstrap = os.path.join(
            settings.PROJECT_ROOT, 'qatrack_core', 'static', 'bootstrap', 'css', 'bootstrap.css'
        )
        with open(bootstrap, encoding='utf8') as f:
            css = f.read()
        assert '.form-horizontal .form-group:after' in css
        assert not re.search(r'^\.form-group:after,?\s*$', css, re.M), (
            'bootstrap now clears a bare .form-group; the explicit clearfix can go'
        )


class TestTheStripeIsActuallyStyled(SimpleTestCase):

    def test_base_css_gives_one_parity_a_background(self):
        with open(BASE_CSS, encoding='utf8') as f:
            rules = tinycss2.parse_stylesheet(f.read(), skip_whitespace=True, skip_comments=True)

        matched = []
        for rule in rules:
            if rule.type != 'qualified-rule':
                continue
            selector = tinycss2.serialize(rule.prelude)
            if 'form-row-even' not in selector:
                continue
            body = tinycss2.serialize(rule.content)
            matched.append((selector.strip(), body))

        assert matched, 'no rule in base.css matches .form-row-even'
        assert any('background' in body for _, body in matched), (
            'a rule matches .form-row-even but none of them sets a background: %r' % matched
        )


BOOTSTRAP_CSS = os.path.join(
    settings.PROJECT_ROOT, 'qatrack_core', 'static', 'bootstrap', 'css', 'bootstrap.css'
)

# How far apart two greys have to be before the difference is one anybody sees
# on a clinical screen. The same figure qa/tests/test_qa_row_striping.py uses.
MIN_GREY_STEP = 10


def grey_level(colour):
    """The 0-255 level a neutral background renders at over white.

    Handles `#rgb`, `#rrggbb` and `rgba(0, 0, 0, a)`; None for anything that is
    not a neutral, since a comparison against a hue would not mean anything.
    """
    if not colour:
        return None
    colour = ' '.join(colour.split())
    m = re.match(r'rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*([0-9.]+)\s*\)$', colour)
    if m:
        return round(255 * (1 - float(m.group(1))))
    m = re.match(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', colour)
    if m:
        digits = m.group(1)
        if len(digits) == 3:
            digits = ''.join(d * 2 for d in digits)
        r, g, b = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
        return r if r == g == b else None
    return None


def background_greys(path, needle, subject_only=True):
    """Grey levels of the backgrounds set by rules whose selector mentions `needle`.

    `subject_only` keeps rules whose *last* compound selector carries it, so a
    rule painting a descendant of a striped row is not counted as the row's own
    colour.
    """
    with open(path, encoding='utf8') as f:
        sheet = tinycss2.parse_stylesheet(f.read(), skip_whitespace=True, skip_comments=True)

    greys = []
    for rule in sheet:
        if rule.type != 'qualified-rule':
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        if needle not in selector:
            continue
        if subject_only and not any(
            needle in part.strip().split()[-1]
            for part in selector.split(',') if part.strip()
        ):
            continue
        body = tinycss2.serialize(rule.content)
        m = re.search(r'background(?:-color)?\s*:\s*([^;}]+)', body)
        level = grey_level(m.group(1) if m else None)
        if level is not None:
            greys.append(level)
    return greys


class TestADisabledControlStillLooksDisabledOnAShadedRow(SimpleTestCase):
    """Bootstrap's own disabled grey sits four levels from the 5% stripe.

    `.form-control[disabled], .form-control[readonly]` is `#eee` (238) and a
    shaded row is 242, so on those rows a disabled control stopped reading as
    disabled. It is not a corner case anyone has to go looking for: `FaultForm`
    lists `related_service_events` sixth, so `forloop.counter` always puts it on
    an even row, and the create form renders that field disabled until a unit is
    chosen - which is the first thing a user sees on the fault page and in the
    fault modal on the perform page.

    Pinned numerically rather than by the existence of a rule, because the
    failure is a gap closing, not a rule disappearing. That is the mistake this
    change already made once on the QC side.
    """

    def test_bootstrap_still_paints_a_disabled_control(self):
        """If this stops being true, the override below has nothing to beat."""
        assert background_greys(BOOTSTRAP_CSS, '.form-control[disabled]'), (
            'bootstrap.css no longer gives a disabled .form-control a neutral '
            'background, so the override in base.css may be unnecessary'
        )

    def test_the_shaded_row_has_a_grey_to_compare(self):
        assert background_greys(BASE_CSS, 'form-row-even'), (
            'no neutral background on .form-row-even, so this proves nothing'
        )

    def test_the_select2_widget_is_covered_too(self):
        """The field this override exists for is a Select2.

        `related_service_events` is rendered by Select2, which hides the native
        select and draws its own widget - so recolouring `.form-control[disabled]`
        alone changed an element nobody can see, while the visible one kept
        select2-bootstrap's own disabled grey. Raised by Copilot on c#31 after
        the first version of this override shipped.
        """
        base = pathlib.Path(BASE_CSS).read_text(encoding='utf8')
        assert '.select2-container--disabled' in base, (
            'nothing in base.css darkens a disabled Select2 widget on a shaded '
            'row, so the fault form still shows one four grey levels from the stripe'
        )
        greys = background_greys(BASE_CSS, '.select2-container--disabled', subject_only=False)
        stripe = background_greys(BASE_CSS, 'form-row-even')
        assert greys, 'the Select2 override sets no neutral background'
        for row in stripe:
            for widget in greys:
                assert abs(row - widget) >= MIN_GREY_STEP, (
                    'a shaded row is %d and a disabled Select2 widget on it is '
                    '%d, %d apart' % (row, widget, abs(row - widget))
                )

    def test_select2_is_what_paints_that_field(self):
        """If Select2 stops being used there, the rule above is dead weight."""
        faults_js = pathlib.Path(
            settings.PROJECT_ROOT, 'faults', 'static', 'faults', 'js', 'faults.js'
        ).read_text(encoding='utf8')
        assert 'related_service_events' in faults_js and 'select2' in faults_js, (
            'faults.js no longer brings Select2 to the related service events '
            'field; the Select2 half of the override can go'
        )

    def test_a_disabled_control_on_a_shaded_row_keeps_its_cue(self):
        stripe = background_greys(BASE_CSS, 'form-row-even')
        override = background_greys(BASE_CSS, '.form-control[disabled]', subject_only=False)
        assert override, (
            'nothing in base.css darkens a disabled control on a shaded row; '
            "bootstrap's #eee (238) is only four levels from the stripe at 242"
        )
        for row in stripe:
            for control in override:
                assert abs(row - control) >= MIN_GREY_STEP, (
                    'a shaded row is %d and a disabled control on it is %d, %d '
                    'apart - under %d the control stops looking disabled'
                    % (row, control, abs(row - control), MIN_GREY_STEP)
                )
