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
  can see it, so the module marks what it reveals readonly. That half is
  exercised in a browser, in qahidden-harness.html.
"""

import os
import re

import tinycss2
from django.conf import settings

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

    def test_there_is_a_reveal_rule(self):
        assert self.reveal_rules(), (
            'no rule in qa.css selects on .%s, so the toggle adds a class that '
            'nothing acts on' % SHOW_CLASS
        )

    def test_the_reveal_shows_the_row(self):
        displays = [
            body for selector, body in self.reveal_rules()
            if 'tr.hidden' in selector and 'display' in body
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
            if 'tr.hidden' not in selector or 'display' not in body:
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
