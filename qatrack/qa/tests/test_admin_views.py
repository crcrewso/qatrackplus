from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import gettext as _

from qatrack.qa import models
from qatrack.qa.tests import utils


class TestListAdminViewsTest(TestCase):
    """Tests for TestList admin views"""

    def setUp(self):
        self.user = utils.create_user(is_superuser=True)
        self.client.force_login(self.user)
        self.test_list = utils.create_test_list()
        self.test = utils.create_test()
        utils.create_test_list_membership(self.test_list, self.test)

    def test_changelist_view_contains_export_import_buttons(self):
        """Test that the changelist view contains export and import buttons"""
        response = self.client.get(reverse('admin:qa_testlist_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin:qa_export_testpack'))
        self.assertContains(response, reverse('admin:qa_import_testpack'))
        self.assertContains(response, _("Export Test Pack"))
        self.assertContains(response, _("Import Test Pack"))

    def test_test_changelist_view_contains_export_import_buttons(self):
        """The Test changelist offers the test pack links too"""
        response = self.client.get(reverse('admin:qa_test_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin:qa_export_testpack'))
        self.assertContains(response, reverse('admin:qa_import_testpack'))
        self.assertContains(response, _("Export Test Pack"))
        self.assertContains(response, _("Import Test Pack"))

    def test_testlistcycle_changelist_view_contains_export_import_buttons(self):
        """The Test List Cycle changelist offers the test pack links too"""
        response = self.client.get(reverse('admin:qa_testlistcycle_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin:qa_export_testpack'))
        self.assertContains(response, reverse('admin:qa_import_testpack'))
        self.assertContains(response, _("Export Test Pack"))
        self.assertContains(response, _("Import Test Pack"))

    def test_export_testpack_view_requires_permission(self):
        """Test that export testpack view requires proper permission"""
        # Remove superuser status and permissions
        self.user.is_superuser = False
        self.user.save()
        response = self.client.get(reverse('admin:qa_export_testpack'))
        self.assertEqual(response.status_code, 403)

        # Add permission
        perm = Permission.objects.get(codename='change_testlist')
        self.user.user_permissions.add(perm)
        response = self.client.get(reverse('admin:qa_export_testpack'))
        self.assertEqual(response.status_code, 200)

    def test_import_testpack_view_requires_permission(self):
        """Test that import testpack view requires proper permission"""
        # Remove superuser status and permissions
        self.user.is_superuser = False
        self.user.save()
        response = self.client.get(reverse('admin:qa_import_testpack'))
        self.assertEqual(response.status_code, 403)

        # Add permission
        perm = Permission.objects.get(codename='change_testlist')
        self.user.user_permissions.add(perm)
        response = self.client.get(reverse('admin:qa_import_testpack'))
        self.assertEqual(response.status_code, 200)

    def test_export_testpack_view_renders_correctly(self):
        """Test that export testpack view renders correctly"""
        response = self.client.get(reverse('admin:qa_export_testpack'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/qa/testpack/export.html')
        self.assertContains(response, self.test_list.name)
        self.assertContains(response, self.test.name)

    def test_import_testpack_view_renders_correctly(self):
        """Test that import testpack view renders correctly"""
        response = self.client.get(reverse('admin:qa_import_testpack'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/qa/testpack/import.html')

    def test_export_import_integration(self):
        """Test that export and import work together"""
        # First export
        response = self.client.post(
            reverse('admin:qa_export_testpack'), {
                'name': 'test-export',
                'description': 'Test export',
                'testlists': str(self.test_list.id),
                'testlistcycles': '',
                'tests': '',
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename=test-export.tpk')

        # Delete the test list and test
        models.TestList.objects.all().delete()
        models.Test.objects.all().delete()

        # Now import
        testpack_data = response.content.decode('utf-8')
        response = self.client.post(
            reverse('admin:qa_import_testpack'),
            {
                'testpack_data': testpack_data,
                'testlists': '[["' + self.test_list.slug + '"]]',  # Natural key format
                'testlistcycles': '[]',
                'tests': '[]',
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Verify the test list and test were imported
        self.assertTrue(models.TestList.objects.filter(slug=self.test_list.slug).exists())
        self.assertTrue(models.Test.objects.filter(slug=self.test.slug).exists())


class TestPackLinksFollowTheirViewsPermission(TestCase):
    """The links must not be offered to users the views will refuse.

    `ExportTestPack` and `ImportTestPack` require `qa.change_testlist`
    (`qa/views/admin.py`), but reaching the Test, Test List or Test List Cycle
    changelist needs only that model's own view or change permission. So a user with
    `qa.view_test` saw both links and got a **403** on clicking either.

    This is a usability defect rather than a security one, and the distinction matters:
    the views were and are the enforcement boundary. These tests assert both halves -
    the link is hidden, *and* the view still refuses - so a later change that swaps the
    template gate for real access control, or drops the view's permission because "the
    link is hidden anyway", fails here.

    Found by @coderabbitai and @copilot-pull-request-reviewer on c#12, which flagged the
    Test and Test List Cycle changelists. **The Test List one has the same defect and
    was not flagged**; it is covered below.
    """

    CHANGELISTS = [
        ('admin:qa_test_changelist', 'view_test'),
        ('admin:qa_testlist_changelist', 'view_testlist'),
        ('admin:qa_testlistcycle_changelist', 'view_testlistcycle'),
    ]

    def setUp(self):
        self.test_list = utils.create_test_list()
        self.test = utils.create_test()
        utils.create_test_list_membership(self.test_list, self.test)
        self.export = reverse('admin:qa_export_testpack')
        self.import_ = reverse('admin:qa_import_testpack')

    def staff_user(self, username, *codenames):
        """A staff user with exactly the named qa permissions and nothing else."""
        user = utils.create_user(uname=username, is_superuser=False, is_staff=True)
        user.user_permissions.clear()
        for codename in codenames:
            user.user_permissions.add(
                Permission.objects.get(content_type__app_label='qa', codename=codename))
        return type(user).objects.get(pk=user.pk)   # clear the permission cache

    def test_the_links_are_hidden_from_a_user_the_views_would_refuse(self):
        for url_name, view_perm in self.CHANGELISTS:
            with self.subTest(changelist=url_name):
                user = self.staff_user('viewer-%s' % view_perm, view_perm)
                self.client.force_login(user)
                response = self.client.get(reverse(url_name))
                assert response.status_code == 200, (url_name, response.status_code)
                self.assertNotContains(response, self.export)
                self.assertNotContains(response, self.import_)

    def test_the_views_still_refuse_that_user(self):
        """The gate is cosmetic; this is the boundary that actually holds."""
        user = self.staff_user('viewer-only', 'view_test', 'view_testlist')
        self.client.force_login(user)
        for url in (self.export, self.import_):
            with self.subTest(url=url):
                assert self.client.get(url).status_code == 403

    def test_the_links_are_shown_to_a_user_who_may_use_them(self):
        """Without this the test above would pass just as well if the links were gone."""
        for url_name, view_perm in self.CHANGELISTS:
            with self.subTest(changelist=url_name):
                user = self.staff_user('editor-%s' % view_perm, view_perm, 'change_testlist')
                self.client.force_login(user)
                response = self.client.get(reverse(url_name))
                assert response.status_code == 200, (url_name, response.status_code)
                self.assertContains(response, self.export)
                self.assertContains(response, self.import_)

    def test_that_user_reaches_the_views(self):
        user = self.staff_user('editor-only', 'view_test', 'change_testlist')
        self.client.force_login(user)
        for url in (self.export, self.import_):
            with self.subTest(url=url):
                assert self.client.get(url).status_code == 200
