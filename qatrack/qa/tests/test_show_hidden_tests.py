"""A test list's hidden tests can be revealed, without that changing a value.

`Test.hidden` means "Don't display this test when performing QC", and in
practice it marks an intermediate value that a composite depends on. The row is
rendered in full and only CSS-hidden, so revealing it is a class on the table -
which is why this is a stylesheet, a template and twenty lines of JavaScript
rather than a change to the form or the view.

Three things have to hold, and each fails independently:

- the toggle is offered only on a list that has something to reveal, so it does
  not appear on the many lists with no hidden tests;
- the stylesheet's reveal actually beats Bootstrap's `.hidden`, which is
  `display: none !important` - an override that loses on specificity is the
  failure nobody notices, because the markup looks right;
- revealing cannot change what is submitted. A composite or constant is readonly
  already; a hidden *simple* test is not, and is unreachable only because nobody
  can see it, so the module marks what it reveals readonly.

**Everything here reads the CSS, the template and the JavaScript as text, and
that is not enough on its own.** Every test in this file passed while a click on
the toggle did nothing whatsoever: the checkbox is wrapped by iCheck, which
reports a click as `ifChanged` and never fires `change`, and `change` was all
the module listened for. crane found that by driving a real browser on
2026-11-06. `TestShowHiddenTests` in `qatrack/qa/tests/test_selenium.py` is the
test that would have caught it, and it is the one to extend when this feature
changes; what is here guards the pieces it cannot see, such as the specificity
of the CSS override.
"""

import os
import re

import tinycss2
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from qatrack.qa import models
from qatrack.qa.tests import utils

QA_CSS = os.path.join(settings.PROJECT_ROOT, 'qa', 'static', 'qa', 'css', 'qa.css')
BOOTSTRAP_CSS = os.path.join(
    settings.PROJECT_ROOT, 'qatrack_core', 'static', 'bootstrap', 'css', 'bootstrap.css'
)
PERFORM_TEMPLATE = os.path.join(
    settings.PROJECT_ROOT, 'qa', 'templates', 'qa', 'testlistinstance_form.html'
)
PERFORM_VIEW = os.path.join(settings.PROJECT_ROOT, 'qa', 'views', 'perform.py')
MODULE = os.path.join(settings.PROJECT_ROOT, 'qa', 'static', 'qa', 'js', 'qahidden.js')
QA_JS = os.path.join(settings.PROJECT_ROOT, 'qa', 'static', 'qa', 'js', 'qa.js')
REQUIREJS_CONFIG = os.path.join(
    settings.PROJECT_ROOT, 'qatrack_core', 'static', 'requirejs', 'js', 'requirejs-config.js'
)
ICHECK_JS = os.path.join(
    settings.PROJECT_ROOT, 'qatrack_core', 'static', 'icheck', 'js', 'icheck.js'
)

SHOW_CLASS = 'show-hidden-tests'


def read(path):
    with open(path, encoding='utf8') as f:
        return f.read()


def rules_matching(path, needle):
    sheet = tinycss2.parse_stylesheet(read(path), skip_whitespace=True, skip_comments=True)
    matched = []
    for rule in sheet:
        if rule.type != 'qualified-rule':
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        if needle in selector:
            matched.append((selector, tinycss2.serialize(rule.content)))
    return matched


def specificity(selector):
    """(ids, classes+attributes+pseudo-classes, elements) for one selector."""
    selector = selector.split(',')[0].strip()
    ids = len(re.findall(r'#[\w-]+', selector))
    classes = len(re.findall(r'\.[\w-]+|\[[^\]]+\]|:[a-z-]+(?!\()', selector))
    elements = len(re.findall(r'(?:^|[\s>+~])([a-zA-Z][\w-]*)', selector))
    return (ids, classes, elements)


class TestTheToggleIsOfferedOnlyWhenThereIsSomethingToReveal:

    def test_the_view_says_whether_the_list_has_hidden_tests(self):
        assert "context['has_hidden_tests'] = any(x.test.hidden for x in self.unit_test_infos)" in read(PERFORM_VIEW), (
            'the perform view no longer reports whether this list has hidden tests, '
            'so the template below cannot decide whether to offer the toggle'
        )

    def test_the_template_gates_the_toggle_on_that_flag(self):
        source = read(PERFORM_TEMPLATE)
        assert 'id="show-hidden-tests"' in source, 'the toggle is gone from the perform page'
        before = source.index('{% if has_hidden_tests %}')
        after = source.index('id="show-hidden-tests"')
        assert before < after, (
            'the toggle is not inside `{% if has_hidden_tests %}`, so it would be '
            'offered on lists with nothing to reveal'
        )


class TestTheRevealBeatsBootstrap:
    """Both rules are !important, so this comes down to specificity."""

    def reveal_rules(self):
        return rules_matching(QA_CSS, SHOW_CLASS)

    @staticmethod
    def controls_the_row_itself(selector):
        """The rule that decides whether the row displays, not one aimed inside it.

        Other rules under the same class legitimately select descendants of the
        revealed row - its cells, and the Skip control that is taken out of
        reach there - and one of those sets `display: none` on purpose. Matching
        on `tr.hidden` appearing anywhere in the selector caught those too, and
        read them as the reveal hiding the row.
        """
        return any(part.strip().endswith('tr.hidden') for part in selector.split(','))

    def test_there_is_a_reveal_rule(self):
        assert self.reveal_rules(), (
            'no rule in qa.css selects on .%s, so the toggle adds a class that '
            'nothing acts on' % SHOW_CLASS
        )

    def test_the_reveal_shows_the_row(self):
        displays = [
            body for selector, body in self.reveal_rules()
            if self.controls_the_row_itself(selector) and 'display' in body
        ]
        assert displays, 'no reveal rule sets a display on tr.hidden'
        for body in displays:
            assert 'none' not in body, 'the reveal rule hides the row: %r' % body
            assert '!important' in body, (
                "the reveal is not !important, so Bootstrap's "
                "`.hidden { display: none !important }` wins: %r" % body
            )

    def test_bootstrap_still_hides_with_important(self):
        """If this stops being true, the !important above is unnecessary."""
        hiding = [
            body for selector, body in rules_matching(BOOTSTRAP_CSS, '.hidden')
            if selector.strip() == '.hidden'
        ]
        assert hiding, 'bootstrap.css no longer has a bare `.hidden` rule'
        assert any('!important' in body for body in hiding), (
            'bootstrap no longer marks `.hidden` !important; the override in '
            'qa.css can be simplified'
        )

    def test_the_reveal_out_specifies_the_rule_it_has_to_beat(self):
        bootstrap = specificity('.hidden')
        for selector, body in self.reveal_rules():
            if not self.controls_the_row_itself(selector) or 'display' not in body:
                continue
            assert specificity(selector) > bootstrap, (
                '%r is %s against bootstrap\'s %s, so with both !important the '
                'row stays hidden' % (selector, specificity(selector), bootstrap)
            )


class TestTheModuleIsWiredUp:

    def test_the_module_is_registered_with_requirejs(self):
        assert "qahidden: siteConfig.STATIC_URL + 'qa/js/qahidden'" in read(REQUIREJS_CONFIG)

    def test_the_perform_script_requires_it_and_calls_it(self):
        source = read(QA_JS)
        assert "'qahidden'" in source, 'qa.js no longer requires the module'
        calls = [
            line.strip() for line in source.splitlines()
            if 'show_hidden_tests(' in line and not line.strip().startswith(('//', '/*', '*'))
        ]
        assert calls, 'qa.js requires the module but never calls it outside a comment'

    def test_the_module_does_not_route_through_show_or_hide(self):
        """`TestInstance.hide()` nulls the value on submit, which would throw
        away the very value a hidden test exists to store.

        Comments are stripped first: the module's own header explains why it
        avoids those calls, and naming them there must not fail this.
        """
        source = re.sub(r'/\*.*?\*/', '', read(MODULE), flags=re.DOTALL)
        source = re.sub(r'^\s*//.*$', '', source, flags=re.MULTILINE)
        for forbidden in ('.show()', '.hide()', 'set_skip'):
            assert forbidden not in source, (
                'qahidden.js uses %s; revealing a test must not touch its '
                'visible state' % forbidden
            )


class TestTheToggleIsWiredToTheEventTheRealPageSends:
    """The failure that every other test in this file missed.

    `sidebar.js` calls `$('.iCheck').iCheck(...)` over the whole page, and the
    menu entry passes a click to iCheck's helper. iCheck 1.0.2 reports the
    change as `ifChanged`/`ifToggled`/`ifChecked`/`ifUnchecked` and never fires
    `change`, so a module that listens for `change` alone is never called. The
    category checkboxes on the same page already listened for `ifChanged`; this
    one did not.
    """

    def test_the_module_listens_for_icheck_s_event(self):
        source = read(MODULE)
        handlers = re.findall(r"""\$toggle\.on\(\s*['"]([^'"]+)['"]""", source)
        assert handlers, "qahidden.js no longer binds a handler to the toggle at all"
        events = ' '.join(handlers).split()
        assert 'ifChanged' in events, (
            "qahidden.js listens for %r. The page's checkbox is wrapped by iCheck, which never "
            "fires 'change', so the toggle will do nothing when a user clicks it." % events
        )
        assert 'change' in events, (
            "qahidden.js listens for %r. Keep 'change' as well: it is what a plain checkbox "
            "sends, and what a test that drives the input directly will fire." % events
        )

    def test_the_toggle_is_the_kind_of_checkbox_icheck_wraps(self):
        """If it ever stops being one, the `ifChanged` above becomes dead weight."""
        template = read(PERFORM_TEMPLATE)
        block = template[template.index('id="menu-show-hidden"'):]
        block = block[:block.index('</li>')]
        assert 'class="iCheck"' in block, (
            "the show-hidden checkbox is no longer marked iCheck, so qahidden.js's 'ifChanged' "
            "binding may no longer be the one that matters - check which event the page sends"
        )

    def test_icheck_still_does_not_fire_change(self):
        """The premise, read from the vendored library rather than assumed."""
        icheck = read(ICHECK_JS)
        assert 'ifChanged' in icheck, "the vendored iCheck no longer mentions ifChanged"
        assert not re.search(r"""callback\(\s*['"]change['"]""", icheck), (
            "the vendored iCheck now appears to fire a 'change' callback; if it does, the "
            "comment in qahidden.js explaining why 'ifChanged' is needed is out of date"
        )


class TestARevealedTestHasMoreThanOneWayToChangeWhatIsSubmitted:
    """A test's row is not all of a test.

    The value box is in `tr.hidden`; the comment box is in a sibling row that
    carries no `hidden` class, and a simple test also has a Skip checkbox. All
    three were unreachable while the row was hidden, and all three have to stay
    that way once it is shown, or the release note's promise is not true.
    """

    def test_the_comment_box_is_locked_too(self):
        source = read(MODULE)
        assert 'tr.qa-comment' in source, (
            "qahidden.js does not reach the comment row, so a comment can be typed on a "
            "revealed hidden test and submitted with it"
        )
        assert 'comment' in source.split('function controls')[1].split('function lock')[0], (
            "the comment row is mentioned but not from the function that collects what to lock"
        )

    def test_the_skip_checkbox_is_put_out_of_reach_by_css(self):
        """Not by `readonly`, which browsers ignore on a checkbox."""
        rules = rules_matching(QA_CSS, 'qa-skip')
        assert rules, (
            "no rule takes the Skip checkbox out of reach on a revealed hidden test, so it can "
            "be clicked and the test submitted as skipped"
        )

    def test_the_skip_checkbox_is_not_disabled_anywhere(self):
        """`disabled` would drop it from the POST, which changes what is submitted."""
        source = read(MODULE)
        assert ".prop('disabled', true)" not in source, (
            "qahidden.js disables a control. A disabled input is not submitted, so the value "
            "the form posts changes - which is the one thing this feature must not do."
        )


class TestTheTemplateDoesNotPrintItsOwnComments:
    """Django's `{# #}` is single-line only; a multi-line one renders as text.

    This happened once on #818's branch and again here, in the same sitting, so
    it is worth a test next to the feature rather than only the repository-wide
    scan on the other branch.
    """

    def test_no_multi_line_hash_comment_in_the_perform_template(self):
        offenders = []
        for number, line in enumerate(read(PERFORM_TEMPLATE).splitlines(), start=1):
            opened = line.count('{#')
            if opened and line.count('#}') < opened:
                offenders.append('%d: %s' % (number, line.strip()))
        assert not offenders, (
            "a `{# ... #}` comment is not closed on its own line, so Django renders it as "
            "visible text on the page:\n  %s" % '\n  '.join(offenders)
        )


class TestTheToggleReachesEveryPageThatRendersTheForm(TestCase):
    """Perform, Edit and Continue all render `qa/testlistinstance_form.html`.

    The toggle is gated on `has_hidden_tests`, so a view that never sets it
    renders the page with the block silently absent - no error, no empty menu
    entry, just a feature that is not there. Neither `EditTestListInstance` nor
    `ContinueTestListInstance` declares a `template_name`, so both inherit that
    template from `ModelFormMixin` and both were missing the flag.

    Asserting that `perform.py` contains the assignment - which this module did
    elsewhere - cannot catch that: the line was present and correct the whole
    time, in the one view that already worked. Only asking a view for a page
    distinguishes the three.
    """

    def setUp(self):
        self.status = utils.create_status()
        self.test_list = utils.create_test_list()

        self.visible = utils.create_test(name="a_visible_test")
        self.hidden = utils.create_test(name="an_intermediate_test")
        self.hidden.hidden = True
        self.hidden.save()

        utils.create_test_list_membership(self.test_list, self.visible)
        utils.create_test_list_membership(self.test_list, self.hidden)

        self.utc = utils.create_unit_test_collection(test_collection=self.test_list)
        self.tli = utils.create_test_list_instance(unit_test_collection=self.utc)
        for test in (self.visible, self.hidden):
            uti = models.UnitTestInfo.objects.get(test=test, unit=self.utc.unit)
            utils.create_test_instance(self.tli, unit_test_info=uti, value=1, status=self.status)

        assert self.client.login(username="user", password="password")

    def urls(self):
        return {
            "perform_qa": reverse("perform_qa", kwargs={"pk": self.utc.pk}),
            "edit_tli": reverse("edit_tli", kwargs={"pk": self.tli.pk}),
            "continue_tli": reverse("continue_tli", kwargs={"pk": self.tli.pk}),
        }

    def test_every_view_offers_the_toggle_when_the_list_has_a_hidden_test(self):
        for name, url in self.urls().items():
            with self.subTest(view=name):
                response = self.client.get(url)
                self.assertEqual(200, response.status_code)
                self.assertContains(
                    response,
                    'id="show-hidden-tests"',
                    msg_prefix=(
                        "%s renders the perform form but does not offer the toggle. "
                        "The view has to put `has_hidden_tests` in its context; the "
                        "template gates the block on it and fails silently without "
                        "it." % name
                    ),
                )

    def test_no_view_offers_the_toggle_when_there_is_nothing_to_reveal(self):
        """The flag is a gate, not a constant - the negative case proves it."""
        self.hidden.hidden = False
        self.hidden.save()

        for name, url in self.urls().items():
            with self.subTest(view=name):
                response = self.client.get(url)
                self.assertEqual(200, response.status_code)
                self.assertNotContains(
                    response,
                    'id="show-hidden-tests"',
                    msg_prefix=(
                        "%s offers the toggle on a list with no hidden tests, so the "
                        "flag is not gating anything" % name
                    ),
                )
