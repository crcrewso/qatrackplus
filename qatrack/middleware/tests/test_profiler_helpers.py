from django.test import TestCase

from qatrack.middleware.profiler import render_queries


class TestProfilerHelperFunctions(TestCase):

    def test_render_queries_order_mode_includes_sql(self):
        queries = [
            {"time": "0.001", "sql": "SELECT 1"},
            {"time": "0.002", "sql": "SELECT 2"},
        ]

        output = render_queries(queries, "order").getvalue()

        assert "SELECT 1" in output
        assert "SELECT 2" in output

    def test_render_queries_rejects_unknown_sort_mode(self):
        with self.assertRaises(RuntimeError):
            render_queries([], "not-a-sort")
