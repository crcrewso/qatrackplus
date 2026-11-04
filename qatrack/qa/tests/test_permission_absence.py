"""What a user *without* a right must not be shown.

Permission tests almost always check that a right lets somebody in. The other
half - that its absence actually withholds something - is the half that goes
untested, and it is where the interesting failures are, because nothing fails
when a page shows too much. A column that should have been hidden renders
perfectly well.

`can_view_history` and `can_view_ref_tol` are the two rights on the perform-QC
page that control what a user is shown rather than what they may do. Before
this file the only test mentioning either was `test_tags.py`, which calls the
colspan tag with a hardcoded permissions dict - so nothing had ever rendered
the page for a user who lacks them.

Worth knowing while reading these: **the view computes the history either
way.** `PerformQA.add_histories()` runs unconditionally and attaches previous
values to every form, and only the template decides whether to render them. So
these tests assert against the rendered page, not the context: the context has
the history in it for every user, by design, and asserting on it would pass
while the page leaked.

Each test comes with its positive control, in the same class, because a page
that showed nothing to anybody would satisfy every negative assertion here.

Asked for by Cody, 2026-11-03.
"""

import json
import re

from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from qatrack.qa import models
from qatrack.qa.tests import utils

# Values nothing else on the page can produce, so finding one in the HTML means
# it leaked rather than something coincidental matching.
#
# PREVIOUS_DISPLAYED is what the history column prints: the value goes through
# a formatter on the way out, so 873.21 renders as 873.2. The negative tests
# look for both, because a change to that formatter must not quietly turn an
# assertion about a leak into an assertion about nothing.
PREVIOUS_VALUE = 873.21
PREVIOUS_DISPLAYED = '873.2'
REFERENCE_VALUE = 500.55


class PerformPageRights(TestCase):
    """One test, one unit, one previous result, and users built per test."""

    def setUp(self):
        self.status = utils.create_status()
        self.test_list = utils.create_test_list()
        self.test = utils.create_test(name="output_constancy")
        utils.create_test_list_membership(self.test_list, self.test, 0)

        self.utc = utils.create_unit_test_collection(test_collection=self.test_list)
        self.uti = models.UnitTestInfo.objects.get(test=self.test, unit=self.utc.unit)
        self.uti.reference = utils.create_reference(value=REFERENCE_VALUE)
        self.uti.tolerance = utils.create_tolerance()
        self.uti.save()

        # The previous session, which is what the history column shows.
        self.previous = utils.create_test_list_instance(
            unit_test_collection=self.utc,
            work_completed=timezone.now() - timezone.timedelta(days=1),
        )
        utils.create_test_instance(
            test_list_instance=self.previous,
            unit_test_info=self.uti,
            value=PREVIOUS_VALUE,
            status=self.status,
        )

        self.url = reverse("perform_qa", kwargs={"pk": self.utc.pk})
        # Whatever the template actually links to, asked of the object the
        # template asks: `history()` builds its dates from
        # `tli.get_absolute_url()`, and which URL that is depends on whether
        # the instance was in progress. Hardcoding a URL name here guessed
        # wrong and made the positive control assert nothing.
        self.previous_session_url = self.previous.get_absolute_url()

    def sign_in_with(self, *codenames):
        """A user holding exactly these qa permissions, and no more.

        Built per test rather than in setUp, because what is under test is the
        difference between two users, and a shared user would have to be
        mutated - which is how permission caching catches people out.
        """
        user = User.objects.create_user('perf-%s' % len(codenames), 'p@example.com', 'pw')
        group, _ = Group.objects.get_or_create(name="group")
        user.groups.add(group)
        for codename in codenames:
            user.user_permissions.add(
                Permission.objects.get(content_type__app_label='qa', codename=codename))
        # Re-read: the permission cache on the instance is populated on first
        # access and would hide anything added after.
        user = User.objects.get(pk=user.pk)
        self.client.force_login(user)
        return user

    def page(self):
        response = self.client.get(self.url)
        assert response.status_code == 200, response.status_code
        return response.content.decode('utf-8')

    def unit_test_infos_json(self, content):
        """The JSON the page hands its JavaScript.

        Parsed rather than grepped, because what matters is which fields are
        in it - a substring search cannot tell a reference value from a
        coincidence, and `500` appears in a page for many reasons.
        """
        found = re.search(r'var unit_test_infos = (\[.*?\]);', content, re.S)
        assert found, "the page no longer emits unit_test_infos"
        return json.loads(found.group(1))


class TestTheHistoryRight(PerformPageRights):

    def test_without_it_the_page_shows_no_previous_results(self):
        """The ask: a form with no previous results on it.

        Three things have to be absent, and they fail independently - the
        column, the value, and the link to the session it came from. A change
        that moved the value out of the column but left it in the row would
        pass a test that only looked for the column.
        """
        self.sign_in_with('add_testlistinstance')
        content = self.page()

        assert 'class="qa-history"' not in content, "the history column rendered"
        assert PREVIOUS_DISPLAYED not in content, "the previous value is on the page"
        assert str(PREVIOUS_VALUE) not in content
        assert self.previous_session_url not in content, (
            "the page links to the previous session, which says there was one")

    def test_with_it_the_previous_result_is_shown(self):
        """The control. Without this the test above passes on a broken page."""
        self.sign_in_with('add_testlistinstance', 'can_view_history')
        content = self.page()

        assert 'class="qa-history"' in content
        assert PREVIOUS_DISPLAYED in content, (
            "the history column rendered but without the value in it")
        assert self.previous_session_url in content

    def test_the_view_attaches_the_history_either_way(self):
        """Asserted because it is the reason these tests read the HTML.

        `add_histories()` is not permission-aware: every form carries the
        previous values whether or not the user may see them, and the template
        is the only thing that withholds them. That is worth having written
        down - it means any new template or any API serializer built on this
        context starts out leaking unless it checks the right itself.
        """
        self.sign_in_with('add_testlistinstance')
        response = self.client.get(self.url)

        forms = response.context['formset'].forms
        histories = [getattr(form, 'history', None) for form in forms]
        assert any(histories), (
            "no form carried history - if add_histories() became "
            "permission-aware, this test should be deleted and the two above "
            "can then assert on the context instead"
        )


class TestTheReferenceAndToleranceRight(PerformPageRights):

    def test_without_it_the_reference_column_is_not_rendered(self):
        self.sign_in_with('add_testlistinstance')
        content = self.page()

        assert 'class="qa-reference"' not in content, "the reference column rendered"

    def test_without_it_the_reference_and_tolerance_are_still_in_the_page_source(self):
        """Documented as found, and it is the finding this file turned up.

        The column is withheld and the numbers are not: `unit_test_infos`, the
        JSON the perform page hands its JavaScript, carries the reference value
        and every tolerance boundary - act_low, tol_low, tol_high, act_high -
        for a user who does not hold `can_view_ref_tol`. View source and they
        are there in full.

        **It is structural rather than an oversight.** qa.js builds a Reference
        and a Tolerance from that blob and computes each test's status in the
        browser; `#pass-fail-only` only rewrites the resulting *message*. So the
        numbers have to be in the page for the status to appear at all, and
        withholding them means computing status server-side instead.

        Whether that is worth doing is a question about what the right is for.
        If `can_view_ref_tol` is meant to stop an operator knowing the window
        they are being measured against - which is the reason a physicist would
        withhold it - then pass/fail feedback already leaks the window by
        bisection, and this makes it a single page-source read instead. If it
        is a UI convenience, there is nothing to fix.

        Asserted so the behaviour is pinned either way: if someone moves status
        computation to the server, this test fails and should be rewritten as
        the negative assertion it would then deserve.
        """
        self.sign_in_with('add_testlistinstance')
        content = self.page()

        blob = self.unit_test_infos_json(content)
        assert blob[0]['reference']['value'] == REFERENCE_VALUE
        assert blob[0]['tolerance']['act_low'] is not None
        assert blob[0]['tolerance']['act_high'] is not None

    def test_the_history_does_not_leak_the_same_way(self):
        """The contrast, and why the one above is a finding rather than a rule.

        `unit_test_infos` carries no previous values at all, for any user, so
        the history right withholds what it claims to. The two rights are
        implemented the same way in the template and differently in the data
        the page ships, which is not something either template makes visible.
        """
        self.sign_in_with('add_testlistinstance')
        raw = self.page()

        assert PREVIOUS_DISPLAYED not in raw
        assert str(PREVIOUS_VALUE) not in raw

    def test_with_it_the_reference_value_is_shown(self):
        self.sign_in_with('add_testlistinstance', 'can_view_ref_tol')
        content = self.page()

        assert 'class="qa-reference"' in content
        assert str(REFERENCE_VALUE) in content

    def test_without_it_the_page_is_put_into_pass_fail_only_mode(self):
        """A second, separate consequence: the JS is told to hide values too.

        `#pass-fail-only` is read by the perform page's JavaScript, which
        decides whether a test's computed status shows the value or only
        pass/fail. Withholding the reference column while leaving this at `no`
        would hide the reference and then display it through the status.
        """
        self.sign_in_with('add_testlistinstance')
        assert 'id="pass-fail-only" value="yes"' in self.page()

    def test_with_it_values_are_shown_rather_than_pass_fail_only(self):
        self.sign_in_with('add_testlistinstance', 'can_view_ref_tol')
        assert 'id="pass-fail-only" value="no"' in self.page()


class TestTheTwoRightsAreIndependent(PerformPageRights):
    """Both columns live inside one `{% if %}`, so they can mask each other.

    The template wraps them in `{% if can_view_ref_tol or can_view_history %}`
    and then tests each right again inside, in two places each - the header row
    in testlistinstance_form.html and the value row in qavalue_form.html. A
    simplification that dropped any of those four inner tests would give a user
    with one right both columns, and the per-right tests above cannot catch it:
    those users hold neither right, so the outer `if` excludes the block before
    the inner ones are reached.

    Measured by dropping each guard in turn. All four inner guards are caught
    here. **Neither outer guard is, and that is correct** - dropping an outer
    `if` changes no page, because the inner guards still withhold both columns.
    The outer ones carry no access control; they are there so the block is
    skipped rather than entered and found empty. Worth knowing before anyone
    treats one of them as the check.
    """

    def test_history_alone_does_not_bring_the_reference_with_it(self):
        self.sign_in_with('add_testlistinstance', 'can_view_history')
        content = self.page()

        assert 'class="qa-history"' in content
        assert 'class="qa-reference"' not in content

    def test_the_reference_alone_does_not_bring_the_history_with_it(self):
        self.sign_in_with('add_testlistinstance', 'can_view_ref_tol')
        content = self.page()

        assert 'class="qa-reference"' in content
        assert 'class="qa-history"' not in content
        assert PREVIOUS_DISPLAYED not in content
