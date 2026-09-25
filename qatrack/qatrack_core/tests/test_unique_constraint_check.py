"""The database is not always enforcing what the models declare.

mssql-django drops a unique index when an unrelated AlterField retypes a
model's primary key, which the 4.0 migrations do to every model, and never
recreates it. Nothing complains: the ORM simply stops raising IntegrityError.
Confirmed against mssql-django 1.7.3, 1.8.0 and 2.0.0; PostgreSQL and SQLite
are unaffected.

These tests run on whatever engine the suite is using, so the ones that need a
missing constraint fake it rather than requiring SQL Server.
"""

from unittest import mock

from django.core.checks import Warning as CheckWarning
from django.db import connection
from django.test import TestCase

from qatrack.qa.models import TestListInstance
from qatrack.qatrack_core.checks import (
    check_unique_constraints_enforced,
    declared_unique_columns,
    enforced_unique_columns,
    unenforced_unique_columns,
)


class TestDeclaredUniqueColumns(TestCase):

    def test_single_unique_field(self):
        declared = declared_unique_columns(TestListInstance)
        assert frozenset(['user_key']) in declared

    def test_primary_key_is_excluded(self):
        # It is unique by construction, and a missing one fails far louder.
        declared = declared_unique_columns(TestListInstance)
        assert frozenset(['id']) not in declared

    def test_unique_together_is_included_as_one_set(self):
        from qatrack.parts.models import Part

        declared = declared_unique_columns(Part)
        assert frozenset(['part_number', 'new_or_used']) in declared

    def test_order_does_not_matter(self):
        # Uniqueness over (a, b) is the same guarantee as over (b, a), and
        # introspection reports whatever order the index used.
        from qatrack.parts.models import Part

        declared = declared_unique_columns(Part)
        assert frozenset(['new_or_used', 'part_number']) in declared

    def test_conditional_constraints_are_skipped(self):
        """A partial index is a different question and this check does not ask it."""
        from django.db.models import Q, UniqueConstraint

        constraint = UniqueConstraint(fields=['user_key'], name='x', condition=Q(in_progress=True))
        with mock.patch.object(TestListInstance._meta, 'constraints', [constraint]):
            declared = declared_unique_columns(TestListInstance)
        # user_key is still there from the field itself, but no extra entry
        # was added for the conditional constraint.
        assert declared == {frozenset(['user_key'])}


class TestUnenforcedComparison(TestCase):

    def test_nothing_missing(self):
        both = {frozenset(['a']), frozenset(['b', 'c'])}
        assert unenforced_unique_columns(both, both) == []

    def test_missing_one(self):
        declared = {frozenset(['a']), frozenset(['b'])}
        enforced = {frozenset(['a'])}
        assert unenforced_unique_columns(declared, enforced) == [['b']]

    def test_a_wider_constraint_does_not_satisfy_a_narrower_one(self):
        # Unique over (a, b) permits duplicate a values, so this must be a set
        # difference and not a subset test.
        declared = {frozenset(['a'])}
        enforced = {frozenset(['a', 'b'])}
        assert unenforced_unique_columns(declared, enforced) == [['a']]

    def test_output_is_deterministic(self):
        declared = {frozenset(['z']), frozenset(['b', 'a']), frozenset(['m'])}
        assert unenforced_unique_columns(declared, set()) == [['m'], ['z'], ['a', 'b']]


class TestCheckBehaviour(TestCase):

    def test_no_database_work_without_the_databases_kwarg(self):
        """Registered under Tags.database, so ordinary commands must skip it."""
        assert check_unique_constraints_enforced(None, databases=None) == []
        assert check_unique_constraints_enforced(None) == []

    def test_this_engine_enforces_everything_it_should(self):
        """On a correctly built schema the check is silent - no false positives."""
        assert check_unique_constraints_enforced(None, databases=['default']) == []

    def test_a_missing_constraint_is_reported(self):
        with mock.patch(
            'qatrack.qatrack_core.checks.enforced_unique_columns', return_value=set()
        ):
            problems = check_unique_constraints_enforced(None, databases=['default'])

        assert problems, "a database enforcing nothing should produce findings"
        assert all(isinstance(p, CheckWarning) for p in problems), "must not be an Error"
        assert all(p.id == 'qatrack.W011' for p in problems)

    def test_it_is_a_warning_not_an_error(self):
        """Checks run before migrate; an Error would abort the fix."""
        with mock.patch(
            'qatrack.qatrack_core.checks.enforced_unique_columns', return_value=set()
        ):
            problems = check_unique_constraints_enforced(None, databases=['default'])
        assert not any(p.is_serious() for p in problems)

    def test_the_hint_gives_runnable_sql(self):
        with mock.patch(
            'qatrack.qatrack_core.checks.enforced_unique_columns', return_value=set()
        ):
            problems = check_unique_constraints_enforced(None, databases=['default'])
        hints = [p.hint for p in problems]
        assert any('CREATE UNIQUE INDEX' in h for h in hints)
        assert any('IS NOT NULL' in h for h in hints), "SQL Server treats NULLs as equal"

    def test_an_unreachable_database_is_not_this_checks_problem(self):
        from django.db.utils import DatabaseError

        with mock.patch.object(
            connection.introspection, 'table_names', side_effect=DatabaseError('nope')
        ):
            assert check_unique_constraints_enforced(None, databases=['default']) == []

    def test_tables_that_do_not_exist_yet_are_skipped(self):
        """First migrate on an empty database must not produce noise."""
        with mock.patch.object(connection.introspection, 'table_names', return_value=[]):
            assert check_unique_constraints_enforced(None, databases=['default']) == []


class TestIntrospectionAgreesWithThisEngine(TestCase):

    def test_enforced_columns_finds_the_user_key_index(self):
        """Guards against the introspection shape changing under us."""
        enforced = enforced_unique_columns(connection, TestListInstance._meta.db_table)
        assert frozenset(['user_key']) in enforced, (
            "this engine should enforce user_key; if it does not, the bug is here too"
        )
