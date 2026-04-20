from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from qatrack.issue_tracker import models


class TestIssueTrackerModels(TestCase):

    def setUp(self):
        self.issue_type = models.IssueType.objects.create(name="Bug")
        self.priority = models.IssuePriority.objects.create(name="High", order=0)
        self.status = models.IssueStatus.objects.create(name="Open", order=0)
        self.tag = models.IssueTag.objects.create(name="Linac")
        self.user = get_user_model().objects.create_user("issue_user")

    def test_issue_priority_string_representation(self):
        assert str(self.priority) == "High"

    def test_issue_status_string_representation(self):
        assert str(self.status) == "Open"

    def test_issue_can_be_created_with_required_relations(self):
        issue = models.Issue.objects.create(
            issue_type=self.issue_type,
            issue_priority=self.priority,
            issue_status=self.status,
            user_submitted_by=self.user,
            datetime_submitted=timezone.now(),
            description="Beam output is unstable",
        )
        issue.issue_tags.add(self.tag)

        assert issue.issue_tags.count() == 1
        assert issue.issue_tags.first().name == "Linac"
