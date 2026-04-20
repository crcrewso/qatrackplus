from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from qatrack.qa.local_site_code import get_local_site_code_calculation_context


class TestLocalSiteCodeContext(TestCase):

    def tearDown(self):
        get_local_site_code_calculation_context.cache_clear()
        super().tearDown()

    @override_settings(LOCAL_SITE_CODE_FUNCTION_MODULES=("local_site_code_sample",))
    def test_loads_sample_functions(self):
        get_local_site_code_calculation_context.cache_clear()

        context = get_local_site_code_calculation_context()

        assert "LSC" in context
        assert "LOCAL_SITE_CODE" in context
        assert context["LSC"].factorial(5) == 120
        assert context["LOCAL_SITE_CODE"].is_prime(13)

    @override_settings(
        LOCAL_SITE_CODE_FUNCTION_MODULES=(
            "local_site_code_sample",
            "local_site_code_sample",
        )
    )
    def test_duplicate_function_names_raise(self):
        get_local_site_code_calculation_context.cache_clear()

        with self.assertRaises(ImproperlyConfigured):
            get_local_site_code_calculation_context()
