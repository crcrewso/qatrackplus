"""A ServiceLog entry whose `extra_info` cannot be read must not 500 the page.

Older `extra_info` values are Python reprs - single-quoted - so they are not JSON. It used to
be read by swapping every `'` for `"` and calling `json.loads`, which corrupts
any value containing an apostrophe. The bare `except` then left the raw
*string* in place and the template tag subscripted it, raising
`TypeError: string indices must be integers` and taking out the whole page.

Measured on a restored clinical database, 2026-10-19: of 4,000 non-empty
values, 119 failed the quote swap - 81 of them for an in-word apostrophe - and
82 of the failures carried a `status_change`, which is the path that
subscripts. `/servicelog/` answered 500 before this change and 200 after, on
that data.
"""

import json
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from qatrack.accounts.tests.utils import create_user
from qatrack.qatrack_core.templatetags.qatrack_tags import parse_extra_info, render_log
from qatrack.service_log import models as sl_models
from qatrack.service_log.tests import utils as sl_utils


class TestParseExtraInfo(SimpleTestCase):

    def test_a_python_repr_is_read(self):
        raw = "{'status_change': {'old': 'Service Pending', 'new': 'Service Complete'}}"
        assert parse_extra_info(raw)['status_change']['old'] == 'Service Pending'

    def test_an_apostrophe_in_a_value_survives(self):
        """The clinical case, and the whole reason for the change.

        The old quote swap turned `don't` into `don"t` and the parse failed.
        """
        raw = "{'status_change': {'old': \"Doesn't apply\", 'new': 'Service Complete'}}"
        parsed = parse_extra_info(raw)
        assert parsed['status_change']['old'] == "Doesn't apply"

    def test_real_json_is_still_read(self):
        raw = '{"status_change": {"old": "a", "new": "b"}}'
        assert parse_extra_info(raw)['status_change']['new'] == 'b'

    def test_a_dict_passes_through(self):
        value = {'status_change': {'old': 'a', 'new': 'b'}}
        assert parse_extra_info(value) is value

    def test_empty_values_give_an_empty_mapping(self):
        for raw in ('', None):
            with self.subTest(raw=raw):
                assert parse_extra_info(raw) == {}

    def test_an_unreadable_value_gives_a_mapping_not_a_string(self):
        """The 500: a string here was subscripted by the caller."""
        parsed = parse_extra_info("this is not a mapping at all")
        assert parsed == {}, parsed
        assert not isinstance(parsed, str)

    def test_a_non_mapping_literal_is_refused(self):
        """`literal_eval` would happily return a list or an int."""
        for raw in ('[1, 2, 3]', '42', "'just a string'"):
            with self.subTest(raw=raw):
                assert parse_extra_info(raw) == {}

    def test_an_unreadable_value_is_logged(self):
        with mock.patch('qatrack.qatrack_core.templatetags.qatrack_tags.logger') as logger:
            parse_extra_info('{not parseable')
        assert logger.warning.called, "a dropped detail should say so"

    def test_it_does_not_evaluate_code(self):
        """`literal_eval`, not `eval` - this is user-influenced data."""
        assert parse_extra_info("__import__('os').system('true')") == {}


class TestParseExtraInfoReadsJsonFirst(SimpleTestCase):

    def test_an_escaped_emoji_comes_back_as_itself(self):
        """ServiceLogManager writes json.dumps, which escapes non-ASCII; literal_eval would split it in two."""
        raw = json.dumps({'status_change': {'old': '\U0001F600', 'new': 'b'}})
        assert parse_extra_info(raw)['status_change']['old'] == '\U0001F600'

    def test_a_list_is_read_when_a_list_is_expected(self):
        raw = json.dumps([{'state': 'tli_reviewed', 'details': 'Daily QA'}])
        assert parse_extra_info(raw, expect=list) == [{'state': 'tli_reviewed', 'details': 'Daily QA'}]

    def test_a_mapping_is_refused_when_a_list_is_expected(self):
        assert parse_extra_info('{"a": 1}', expect=list) == []


class TestRenderLogWithUnusualExtraInfo(TestCase):

    def setUp(self):
        self.user = create_user(is_superuser=True)
        self.service_event = sl_utils.create_service_event()

    def render(self, log_type, extra_info):
        log = sl_models.ServiceLog.objects.create(
            user=self.user, service_event=self.service_event, log_type=log_type, extra_info=extra_info
        )
        return render_log(log, self.user)

    def test_return_to_service_changes_are_listed(self):
        """create_rts_log_details() records a list; reading it as a mapping showed 'All Deleted'."""
        html = self.render(sl_models.CHANGED_RTSQA, json.dumps([{'state': 'tli_reviewed', 'details': 'Daily QA'}]))
        assert 'Daily QA' in html
        assert 'All Deleted' not in html

    def test_an_unreadable_status_change_renders(self):
        """A status entry whose detail cannot be read still renders, rather than raising KeyError."""
        html = self.render(sl_models.STATUS_SERVICE_EVENT, '{not parseable')
        assert 'changed status of service event' in html

    def test_a_status_change_renders_with_a_cold_colour_cache(self):
        cache.delete(settings.CACHE_SERVICE_STATUS_COLOURS)
        raw = json.dumps({'status_change': {'old': 'a', 'new': 'b'}, 'other_changes': {}})
        html = self.render(sl_models.STATUS_SERVICE_EVENT, raw)
        assert 'changed status of service event' in html
