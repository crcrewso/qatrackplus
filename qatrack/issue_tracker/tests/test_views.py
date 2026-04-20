from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from qatrack.issue_tracker import models


class TestIssueTrackerViews(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user("issue_user", password="pwd")
        self.issue_type = models.IssueType.objects.create(name="Bug")
        self.priority = models.IssuePriority.objects.create(name="High", order=0)
        models.IssueStatus.objects.create(name="Open", order=0)
        self.tag = models.IssueTag.objects.create(name="Linac")

    def test_issue_new_requires_login(self):
        response = self.client.get(reverse("issue_new"))
        assert response.status_code == 302

    def test_issue_new_creates_issue_when_authenticated(self):
        self.client.login(username="issue_user", password="pwd")

        payload = {
            "issue_type": self.issue_type.pk,
            "issue_priority": self.priority.pk,
            "issue_tags": [self.tag.pk],
            "description": "Daily QA trend not loading",
            "error_screen": "Traceback ...",
        }
        response = self.client.post(reverse("issue_new"), payload)

        assert response.status_code == 302
        assert models.Issue.objects.count() == 1

    def test_issue_list_requires_login(self):
        response = self.client.get(reverse("issue_list"))
        assert response.status_code == 302
