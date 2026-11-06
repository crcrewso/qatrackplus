"""#818: the QC tables shade alternate tests, as the plain forms shade
alternate rows.

The QC tables cannot reuse the forms' `forloop.counter` mechanism - a test is a
block of two to five rows, and the perform page hides whole tests at runtime -
so the class is added by `qa/js/qastripe.js` instead. That splits the feature
across three files, and each of them can be right on its own while the page
looks unchanged:

- the stylesheet has to give the class a background. A class no rule matches is
  the failure nobody notices;
- the class the script adds has to be the class the stylesheet names;
- both tables have to carry the hook the stylesheet selects on, and both page
  scripts have to load the module and call it.

Two further properties are worth pinning because losing either would be a
regression nobody would report as one:

- the stripe must not outrank the focus highlight that says "you are here"
  while a test is being entered, and must not depend on the two rules' order in
  the file to lose to it;
- calculated values - composite and constant tests - are told apart by their
  readonly input's own background, not by a row colour. Striping the rows must
  not be mistaken for that cue and replace it.

The stylesheets are parsed with tinycss2, which arrives with WeasyPrint, the
same way `reports/tests/test_schedule_dialog_css.py` does it.
"""

import os
import re

import tinycss2
from django.conf import settings
from django.test import SimpleTestCase

STATIC = settings.PROJECT_ROOT
QA_CSS = os.path.join(STATIC, 'qa', 'static', 'qa', 'css', 'qa.css')
BASE_CSS = os.path.join(STATIC, 'qatrack_core', 'static', 'qatrack_core', 'css', 'base.css')
QASTRIPE_JS = os.path.join(STATIC, 'qa', 'static', 'qa', 'js', 'qastripe.js')
QA_JS = os.path.join(STATIC, 'qa', 'static', 'qa', 'js', 'qa.js')
QAREVIEW_JS = os.path.join(STATIC, 'qa', 'static', 'qa', 'js', 'qareview.js')
REQUIREJS_CONFIG = os.path.join(
    STATIC, 'qatrack_core', 'static', 'requirejs', 'js', 'requirejs-config.js'
)
PERFORM_TEMPLATE = os.path.join(STATIC, 'qa', 'templates', 'qa', 'testlistinstance_form.html')
REVIEW_TEMPLATE = os.path.join(STATIC, 'qa', 'templates', 'qa', 'testlistinstance_review.html')

STRIPE_CLASS = 'qa-row-even'

# How far apart two greys have to be before the difference is one anybody sees
# on a clinical screen. 2.5% vs 5% black on white is 6 levels and was reported
# as "not obvious"; the three shades in use are 255, 242 and 227.
MIN_GREY_STEP = 10


def read(path):
    with open(path, encoding='utf8') as f:
        return f.read()


def rules_matching(path, needle):
    """(selector, body) for every qualified rule whose selector mentions
    `needle`."""
    sheet = tinycss2.parse_stylesheet(read(path), skip_whitespace=True, skip_comments=True)
    matched = []
    for rule in sheet:
        if rule.type != 'qualified-rule':
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        if needle in selector:
            matched.append((selector, tinycss2.serialize(rule.content)))
    return matched


def grey_level(colour):
    """The 0-255 level a neutral background renders at on a white table, for
    `#rgb`, `#rrggbb` and `rgba(0, 0, 0, a)`. None if it is not a neutral."""
    if colour is None:
        return None
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


def background_colour(body):
    m = re.search(r'background(?:-color)?\s*:\s*([^;}]+)', body)
    return m and ' '.join(m.group(1).split())


class TestTheStripeIsStyled(SimpleTestCase):

    def test_qa_css_gives_the_stripe_class_a_background(self):
        matched = rules_matching(QA_CSS, STRIPE_CLASS)
        assert matched, 'no rule in qa.css matches .%s' % STRIPE_CLASS
        assert any(background_colour(body) for _, body in matched), (
            'a rule matches .%s but none of them sets a background: %r' % (STRIPE_CLASS, matched)
        )

    def test_the_script_adds_the_class_the_stylesheet_names(self):
        """Either half can be right while the page looks unchanged."""
        m = re.search(r"STRIPE_CLASS\s*=\s*'([^']+)'", read(QASTRIPE_JS))
        assert m, 'qastripe.js no longer declares a STRIPE_CLASS'
        assert m.group(1) == STRIPE_CLASS, (
            'qastripe.js adds .%s but qa.css styles .%s' % (m.group(1), STRIPE_CLASS)
        )

    def test_the_qc_stripe_is_the_same_shade_as_the_form_stripe(self):
        """The two halves of #818 are one visual decision, so they must not be
        tuned apart by accident."""
        qc = [background_colour(body) for _, body in rules_matching(QA_CSS, STRIPE_CLASS)]
        form = [background_colour(body) for _, body in rules_matching(BASE_CSS, 'form-row-even')]
        qc = [c for c in qc if c]
        form = [c for c in form if c]
        assert qc and form, (qc, form)
        assert set(qc) == set(form), (
            'the QC tables stripe with %r and the forms with %r' % (qc, form)
        )


class TestTheStripeLosesToTheFocusHighlight(SimpleTestCase):
    """While a test is being entered its row is highlighted, and that has to
    win: a stripe that outranks it defeats the point of saying "you are here".
    """

    def highlight_rules(self):
        return [
            (selector, body) for selector, body in rules_matching(QA_CSS, 'tr.hover')
            if background_colour(body)
        ]

    def test_the_focus_highlight_still_sets_a_background(self):
        assert self.highlight_rules(), 'no rule in qa.css gives tr.hover a background'

    def test_the_highlight_is_still_visibly_darker_than_the_stripe(self):
        """Specificity only settles which rule wins. If the two greys are close
        enough, the highlight wins and still looks like nothing happened -
        which is how raising the stripe from 2.5% to 5% nearly lost it: that
        left four levels of grey between a shaded row and a focused one."""
        stripe = [background_colour(body) for _, body in rules_matching(QA_CSS, STRIPE_CLASS)]
        stripe = [grey_level(c) for c in stripe if c]
        focus = [grey_level(background_colour(body)) for _, body in self.highlight_rules()]
        assert stripe and focus, (stripe, focus)
        assert None not in stripe and None not in focus, (
            'the stripe or the highlight is no longer a plain grey, so this '
            'comparison needs rewriting: %r %r' % (stripe, focus)
        )
        assert max(focus) <= min(stripe) - MIN_GREY_STEP, (
            'a focused row is %r and a shaded row %r on a white table: fewer than '
            '%d levels apart, so the highlight no longer reads as one'
            % (focus, stripe, MIN_GREY_STEP)
        )

    def test_the_highlight_outranks_the_stripe_on_specificity_alone(self):
        """Not on source order, which a later edit could reverse without
        anyone noticing."""
        for selector, _body in rules_matching(QA_CSS, STRIPE_CLASS):
            assert '#' not in selector, (
                'the stripe selector %r uses an id, so it can out-specify the focus '
                'highlight' % selector
            )
        for selector, _body in self.highlight_rules():
            assert '#' in selector, (
                'the focus highlight %r no longer uses an id, so it no longer outranks '
                'the stripe on specificity' % selector
            )


class TestCalculatedValuesKeepTheirOwnCue(SimpleTestCase):
    """Composite and constant tests render a readonly input, and that input's
    background - not the row's - is what tells a calculated value apart. The
    row striping is a second, independent axis and must not displace it."""

    def test_a_readonly_qa_input_still_has_its_own_background(self):
        matched = [
            (selector, body) for selector, body in rules_matching(QA_CSS, 'readonly')
            if background_colour(body)
        ]
        assert matched, (
            'no rule in qa.css gives input[readonly].qa-input a background, so a '
            'calculated value no longer looks different from an entered one'
        )

    def test_the_cue_is_on_the_input_not_the_row(self):
        for selector, _body in rules_matching(QA_CSS, STRIPE_CLASS):
            assert 'readonly' not in selector, selector


class TestBothPagesAreWiredUp(SimpleTestCase):

    def test_the_module_is_registered_with_requirejs(self):
        assert "qastripe: siteConfig.STATIC_URL + 'qa/js/qastripe'" in read(REQUIREJS_CONFIG)

    def test_both_tables_carry_the_hook_the_stylesheet_selects_on(self):
        for path, table_id in ((PERFORM_TEMPLATE, 'perform-qa-table'), (REVIEW_TEMPLATE, 'review-table')):
            m = re.search(r'<table id="%s"[^>]*class="([^"]*)"' % table_id, read(path))
            assert m, 'no <table id="%s"> with a class attribute in %s' % (table_id, path)
            assert 'qa-table' in m.group(1).split(), (
                '<table id="%s"> does not carry qa-table, so .qa-table > tbody > tr.%s '
                'cannot match its rows' % (table_id, STRIPE_CLASS)
            )

    def test_both_page_scripts_load_the_module_and_call_it(self):
        for path in (QA_JS, QAREVIEW_JS):
            source = read(path)
            assert "'qastripe'" in source, '%s does not require qastripe' % path
            assert 'stripe_qa_rows(' in source, '%s never calls the striper' % path

    def test_the_perform_page_restripes_when_the_category_filter_changes(self):
        """The filter hides whole tests, which is the reason this is script at
        all; striping once on load would leave it wrong from the first
        filter."""
        source = read(QA_JS)
        subscribers = [m.end() for m in re.finditer(r'Topic\("categoryFilter"\)\.subscribe\(', source)]
        assert subscribers, 'qa.js no longer subscribes to categoryFilter'
        assert any('stripe_qa_rows' in source[end:end + 400] for end in subscribers), (
            'qa.js subscribes to categoryFilter %d time(s) but none of them restripes'
            % len(subscribers)
        )
