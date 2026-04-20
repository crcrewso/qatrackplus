from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from qatrack.middleware.login_required import LoginRequiredMiddleware


class TestLoginRequiredMiddleware(TestCase):

    @override_settings(LOGIN_URL="/accounts/login/", LOGIN_EXEMPT_URLS=[r"^accounts/login/$"])
    def test_anonymous_user_redirected_for_protected_path(self):
        request = RequestFactory().get("/qa/")
        request.user = AnonymousUser()

        middleware = LoginRequiredMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)

        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]

    @override_settings(LOGIN_URL="/accounts/login/", LOGIN_EXEMPT_URLS=[r"^accounts/login/$"])
    def test_anonymous_user_can_access_exempt_login_path(self):
        request = RequestFactory().get("/accounts/login/")
        request.user = AnonymousUser()

        middleware = LoginRequiredMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)

        assert response.status_code == 200
