from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from qatrack.middleware.maintain_filters import FilterPersistMiddleware


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: HttpResponse("ok"))
    middleware.process_request(request)
    request.session.save()


class TestFilterPersistMiddleware(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user("mw_user")

    def test_non_admin_paths_are_not_modified(self):
        request = RequestFactory().get("/qa/")
        request.user = self.user
        request.META["HTTP_REFERER"] = "http://testserver/"
        _attach_session(request)

        middleware = FilterPersistMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)

        assert response.status_code == 200

    def test_admin_filter_query_is_saved_in_session(self):
        request = RequestFactory().get("/admin/qa/test/?status=1")
        request.user = self.user
        request.META["QUERY_STRING"] = "status=1"
        request.META["HTTP_REFERER"] = "http://testserver/admin/qa/test/"
        _attach_session(request)

        middleware = FilterPersistMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)

        assert response.status_code == 200
        assert request.session.get("key_admin_qa_test_") == "status=1"
