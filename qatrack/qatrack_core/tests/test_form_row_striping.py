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
