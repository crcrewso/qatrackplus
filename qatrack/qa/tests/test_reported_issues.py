"""Reproductions of user-reported issues, each named for its upstream issue.

Every test here was written to fail on 4.0.2 (`e0936698`) before its fix landed,
except the ones marked ``xfail``, which document a defect whose fix lives in a
dependency.
"""

import json
import types

import pytest
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from qatrack.qa import models, views
from qatrack.qa.admin import FrequencyForm
from qatrack.qa.templatetags.qa_tags import history_display
from qatrack.qa.tests import utils
from qatrack.qatrack_core.dates import format_as_date


class TestIssue654SpecificDatesOnly(TestCase):
    """#654: a Frequency made of specific dates and nothing else was rejected as
    'exclusion rules only'."""

    def form(self, recurrences):
        return FrequencyForm(data={
            'name': "dates", 'slug': "dates", 'window_start': '', 'window_end': 1, 'recurrences': recurrences,
        })

    def test_specific_dates_only_is_valid(self):
        form = self.form("RDATE:20261105T050000Z\nRDATE:20261220T050000Z")
        assert form.is_valid(), form.errors
        frequency = form.save()
        assert frequency.nominal_interval > 0

    def test_exclusions_only_is_still_rejected(self):
        form = self.form("EXDATE:20261105T050000Z")
        assert not form.is_valid()
        assert "exclusion rules only" in str(form.errors['recurrences'])

    def test_a_rule_is_still_valid(self):
        assert self.form("RRULE:FREQ=WEEKLY").is_valid()


class CompositeSetup(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = views.perform.CompositeCalculation.as_view()
        self.url = reverse("composite")
        self.user = utils.create_user()
        self.unit = utils.create_unit()
        self.test_list = utils.create_test_list()
        self.t1 = utils.create_test(name="test1")
        self.tc = utils.create_test(name="testc", test_type=models.COMPOSITE)
        for t in [self.t1, self.tc]:
            utils.create_test_list_membership(self.test_list, t)
            utils.create_unit_test_info(test=t, unit=self.unit)

    def calculate(self, tests, **extra):
        data = {
            'tests': tests,
            'meta': {},
            'test_list_id': self.test_list.id,
            'unit_id': self.unit.id,
            'skips': {},
        }
        data.update(extra)
        request = self.factory.post(self.url, content_type='application/json', data=json.dumps(data))
        request.user = self.user
        return json.loads(self.view(request).content.decode("UTF-8"))


class TestIssue570CompositeErrors(CompositeSetup):
    """#570: any exception in a composite whose inputs were still blank was
    hidden, so a procedure that could not even compile showed nothing."""

    def test_syntax_error_is_shown_even_with_blank_inputs(self):
        self.tc.calculation_procedure = "result = test1 +"
        self.tc.save()

        result = self.calculate({"test1": "", "testc": ""})["results"]["testc"]

        assert result["error"] is not None
        assert "Invalid Test Procedure" in result["error"]

    def test_runtime_error_with_blank_input_is_still_quiet(self):
        self.tc.calculation_procedure = "result = test1 + 1"
        self.tc.save()

        result = self.calculate({"test1": "", "testc": ""})["results"]["testc"]

        assert result["error"] is None

    def test_runtime_error_with_complete_inputs_is_shown(self):
        self.tc.calculation_procedure = "result = test1 + undefined_name"
        self.tc.save()

        result = self.calculate({"test1": 1, "testc": ""})["results"]["testc"]

        assert result["error"] is not None


class TestIssue680BooleanDefault(CompositeSetup):
    """#680: a calculated default of False for a boolean test showed as True.

    The page's script compared the default to the number 0, but a Python False
    arrives as JSON false. This test pins the server half of the contract: the
    default is delivered as a boolean, which is what ``qa.js`` now accepts.
    """

    def test_boolean_default_is_delivered_as_false(self):
        tb = utils.create_test(name="testb", test_type=models.BOOLEAN)
        tb.calculation_procedure = "result = False"
        tb.save()
        utils.create_test_list_membership(self.test_list, tb)
        utils.create_unit_test_info(test=tb, unit=self.unit)

        result = self.calculate({"test1": "", "testc": "", "testb": ""}, defaults=True)["results"]["testb"]

        assert result["value"] is False
        assert result["error"] is None


class TestIssue658HistoryChartRange(TestCase):
    """#658: the chart link beside a history table ended on the newest history
    row, which on a review page is the result *before* the one being reviewed."""

    def test_chart_range_reaches_today(self):
        now = timezone.now()
        old = now - timezone.timedelta(days=40)
        older = now - timezone.timedelta(days=80)
        history = [
            (types.SimpleNamespace(work_completed=old), None),
            (types.SimpleNamespace(work_completed=older), None),
        ]
        unit = utils.create_unit()
        test_list = utils.create_test_list()
        test = utils.create_test(name="t")

        html = history_display(history, unit, test_list, test)

        assert format_as_date(now) in html
        assert ("- %s" % format_as_date(old)) not in html


class TestIssue662UploadError(TransactionTestCase):
    """#662: a media directory the server cannot write to produced a bare
    traceback (or, in 3.x, an unrelated message) on the upload button."""

    def setUp(self):
        self.user = utils.create_user()
        self.unit = utils.create_unit()
        self.test_list = utils.create_test_list()
        self.tu = utils.create_test(name="testu", test_type=models.UPLOAD)
        self.tu.calculation_procedure = "result = 1"
        self.tu.save()
        utils.create_test_list_membership(self.test_list, self.tu)
        utils.create_unit_test_info(test=self.tu, unit=self.unit)
        self.client.force_login(self.user)

    def test_unwritable_media_root_says_so(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with override_settings(MEDIA_ROOT="/dev/null/not-a-directory"):
            resp = self.client.post(
                reverse("upload"),
                {
                    'upload': SimpleUploadedFile("data.txt", b"1,2,3"),
                    'test_id': self.tu.id,
                    'test_list_id': self.test_list.id,
                    'unit_id': self.unit.id,
                    'meta': json.dumps({}),
                    'comments': json.dumps({}),
                },
            )
        body = json.loads(resp.content.decode("UTF-8"))
        assert body["success"] is False
        assert "could not be saved" in body["errors"][0]
        assert "/dev/null/not-a-directory" in body["errors"][0]
        assert "Traceback" not in body["errors"][0]


class TestIssue674AvailableTimePermission(TestCase):
    """#674: the sidebar tested ``perms.units.change_unitavailable_time``, a
    codename that does not exist, so only staff ever saw the link."""

    def test_user_with_the_permission_sees_the_link(self):
        user = utils.create_user(is_staff=False, is_superuser=False)
        user.user_permissions.add(Permission.objects.get(codename="change_unitavailabletime"))
        self.client.force_login(user)

        resp = self.client.get(reverse("home"))

        assert resp.status_code == 200
        assert "Unit Available Times" in resp.content.decode("UTF-8")

    def test_user_without_it_does_not(self):
        user = utils.create_user(is_staff=False, is_superuser=False)
        self.client.force_login(user)

        resp = self.client.get(reverse("home"))

        assert resp.status_code == 200
        assert "Unit Available Times" not in resp.content.decode("UTF-8")


class TestIssue713AccentedFilter(TestCase):
    """#713: filtering the QC list by a site named with an accent returned
    nothing.

    The column filter escapes option values with JavaScript's ``escape()``,
    which writes ``ô`` as ``%F4``; django-listable then runs that through
    ``urllib.parse.unquote`` as UTF-8, where ``%F4`` alone is invalid and
    becomes U+FFFD. The fix belongs in django-listable's ``unquote_unicode``.
    """

    @pytest.mark.xfail(strict=True, reason="django-listable 0.9.4 decodes escape()'s %F4 as UTF-8 (upstream #713)")
    def test_filter_by_accented_site_name(self):
        utils.create_status()
        here = utils.create_site(name="Hôpital X")
        elsewhere = utils.create_site(name="Other")
        test_list = utils.create_test_list()
        utils.create_unit_test_collection(unit=utils.create_unit(name="u1", site=here), test_collection=test_list)
        utils.create_unit_test_collection(unit=utils.create_unit(name="u2", site=elsewhere), test_collection=test_list)
        self.client.force_login(utils.create_user(is_superuser=True))

        resp = self.client.get(
            reverse("all_lists"),
            {'sEcho': 1, 'iDisplayStart': 0, 'iDisplayLength': 10, 'sSearch_3': '^(H%F4pital%20X)$'},
            headers={"x-requested-with": 'XMLHttpRequest'}
        )

        assert resp.status_code == 200
        assert json.loads(resp.content.decode("UTF-8"))["iTotalDisplayRecords"] == 1
