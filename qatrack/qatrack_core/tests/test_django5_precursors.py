"""The forward-compatible half of the Django 5 move, pinned down on Django 4.2.

Each test here passes on 4.2 and describes a behaviour that Django 5.x makes
mandatory (POST-only logout, no related filters on unsaved instances, no
``delete()`` on a DeleteView) or that a dependency has already removed
(``pydicom.read_file``). See aviary backlog B121.
"""

import warnings

import pydicom
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils.deprecation import RemovedInDjango50Warning
from pydicom.data import get_testdata_file

from qatrack.attachments import utils as attachment_utils
from qatrack.parts import models as parts_models
from qatrack.qa import models
from qatrack.qa.tests import utils


class TestUnsavedTestSignal(TestCase):
    """Django 5.0 raises when an unsaved instance is used in a related filter;
    4.2 warns. ``on_test_save`` filtered UnitTestInfo on a Test being created."""

    def test_creating_a_boolean_test_emits_no_unsaved_filter_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            utils.create_test(name="bool", test_type=models.BOOLEAN)
        unsaved = [w for w in caught if issubclass(w.category, RemovedInDjango50Warning) and "unsaved" in str(w.message)]
        assert unsaved == []


class TestLogoutIsAForm(TestCase):
    """Django 5.0's LogoutView accepts POST only, so a GET link returns 405
    there. The pages now carry a form, which 4.2 accepts as well."""

    def test_sidebar_logs_out_by_post(self):
        self.client.force_login(utils.create_user())
        html = self.client.get(reverse("home")).content.decode("UTF-8")
        assert 'method="post" action="%s"' % reverse("auth_logout") in html
        assert 'href="%s"' % reverse("auth_logout") not in html

    def test_post_logout_works(self):
        self.client.force_login(utils.create_user())
        resp = self.client.post(reverse("auth_logout"))
        assert resp.status_code in (200, 302)
        assert "_auth_user_id" not in self.client.session


class TestDeleteViewsUseFormValid(TestCase):
    """Since Django 4.0 a POST to a DeleteView runs form_valid(), never
    delete(); 4.2 warns about a delete() override and 5.0 stops warning. The
    cleanup that lived in delete() therefore never ran on a POST."""

    def test_deleting_a_fault_removes_its_comments_and_reports_it(self):
        from django.contrib.contenttypes.models import ContentType
        from django_comments.models import Comment

        from qatrack.faults import models as fault_models
        from qatrack.faults.tests import utils as fault_utils

        user = utils.create_user(is_superuser=True)
        self.client.force_login(user)
        fault = fault_utils.create_fault()
        Comment.objects.create(
            content_type=ContentType.objects.get_for_model(fault_models.Fault),
            object_pk=str(fault.pk),
            site_id=1,
            user=user,
            comment="about this fault",
        )

        resp = self.client.post(reverse("fault_delete", kwargs={'pk': fault.pk}), follow=True)

        assert resp.status_code == 200
        assert not fault_models.Fault.objects.filter(pk=fault.pk).exists()
        assert not Comment.objects.filter(object_pk=str(fault.pk)).exists()
        assert "Successfully deleted Fault %d" % fault.pk in resp.content.decode("UTF-8")

    def test_deleting_a_test_list_instance_by_post(self):
        user = utils.create_user(is_superuser=True)
        self.client.force_login(user)
        utils.create_status()
        tli = utils.create_test_list_instance()

        resp = self.client.post(reverse("delete_test_list_instance", kwargs={'pk': tli.pk}))

        assert resp.status_code == 302
        assert not models.TestListInstance.objects.filter(pk=tli.pk).exists()


class TestPydicomDcmread(TestCase):
    """``pydicom.read_file`` is gone in pydicom 3; ``dcmread`` is on 2.x too."""

    def test_dicom_attachment_renders_to_png(self):
        path = get_testdata_file("CT_small.dcm")
        with open(path, "rb") as f:
            png = attachment_utils.imsave(f, "image.png")
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert pydicom.dcmread(path, force=True).pixel_array is not None


class TestTableFormRenderer(TestCase):
    """Django 4.2 renders ``{{ form }}`` through ``default.html`` and warns that
    5.0 switches to divs; naming the table template keeps the layout and the
    silence on both."""

    def test_rendering_a_form_warns_about_nothing(self):
        from django import forms

        class F(forms.Form):
            name = forms.CharField()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            html = str(F())
        assert "<tr>" in html
        assert [w for w in caught if issubclass(w.category, RemovedInDjango50Warning)] == []


class TestSupplierWebsiteTag(TestCase):
    """``format_html`` with the values as arguments escapes them; calling it
    with a preformatted string is deprecated in Django 5.0 and was not escaping
    anything."""

    def test_website_is_escaped(self):
        supplier = parts_models.Supplier(name="s", website='https://example.com/?a="b"')
        tag = supplier.get_website_tag()
        assert '&quot;b&quot;' in tag
        assert '"b"' not in tag.replace('&quot;', '')


class TestPermissionsStillApply(TestCase):
    """The moved delete logic must not loosen the permission check."""

    def test_fault_delete_needs_permission(self):
        from qatrack.faults.tests import utils as fault_utils

        user = utils.create_user(is_superuser=False, is_staff=False)
        user.user_permissions.remove(*Permission.objects.filter(codename="delete_fault"))
        self.client.force_login(user)
        fault = fault_utils.create_fault()

        resp = self.client.post(reverse("fault_delete", kwargs={'pk': fault.pk}))

        assert resp.status_code == 403
