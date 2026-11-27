"""`qatrack.W016`: hidden tests of a type somebody has to enter."""

from unittest import mock

from django.test import TestCase

from qatrack.qa import models
from qatrack.qa.tests import utils
from qatrack.qatrack_core.checks import check_hidden_tests_are_not_user_entered


class TestHiddenTestsCheck(TestCase):

    def hidden(self, test_type, name):
        test = utils.create_test(name=name, test_type=test_type)
        models.Test.objects.filter(pk=test.pk).update(hidden=True)
        return test

    def test_a_hidden_simple_test_is_reported(self):
        self.hidden(models.SIMPLE, "typed_in")
        problems = check_hidden_tests_are_not_user_entered(None, databases=["default"])
        assert [p.id for p in problems] == ["qatrack.W016"]
        assert "typed_in" in problems[0].msg

    def test_a_hidden_composite_is_not_reported(self):
        self.hidden(models.COMPOSITE, "computed")
        assert check_hidden_tests_are_not_user_entered(None, databases=["default"]) == []

    def test_nothing_runs_without_a_database_argument(self):
        self.hidden(models.SIMPLE, "typed_in")
        assert check_hidden_tests_are_not_user_entered(None) == []

    def test_each_database_it_is_given_is_the_one_queried(self):
        """`check --database other` has to look at `other`, not wherever the router points."""
        real_using = models.Test.objects.using
        with mock.patch.object(models.Test.objects, "using", side_effect=real_using) as using:
            check_hidden_tests_are_not_user_entered(None, databases=["default"])
        assert [call.args for call in using.call_args_list] == [("default",)]

    def test_the_same_database_reached_twice_is_counted_once(self):
        """As `readonly` mirrors `default` on a site; pytest drops that alias, so `default` is named twice."""
        self.hidden(models.SIMPLE, "typed_in")
        problems = check_hidden_tests_are_not_user_entered(None, databases=["default", "default"])
        assert problems[0].msg.startswith("1 test hidden"), problems[0].msg
