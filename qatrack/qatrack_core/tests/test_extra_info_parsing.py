"""A ServiceLog entry whose `extra_info` cannot be read must not 500 the page.

`extra_info` holds Python reprs - single-quoted - so it is not JSON. It used to
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

from unittest import mock

from django.test import SimpleTestCase

from qatrack.qatrack_core.templatetags.qatrack_tags import parse_extra_info


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
