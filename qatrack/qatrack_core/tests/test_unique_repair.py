"""The repair that puts back unique constraints the database stopped enforcing.

These run on whatever engine the suite is using. That is possible *because* the repair
names no engine: its decisions come from introspecting the database in front of it, so
the decision logic can be asserted anywhere. An earlier version guarded on
`connection.vendor == 'microsoft'`, and nothing about it could be tested except on SQL
Server.
"""

from django.apps import apps
from django.db import connection
from django.db.models import Q
from django.test import TestCase, TransactionTestCase

from qatrack.parts.models import Contact, Room
from qatrack.qa.models import TestListInstance
from qatrack.qatrack_core.unique_repair import (
    _build,
    constraint_name,
    remove_repaired_constraints,
    repair_unique_constraints,
)

SPECS = [
    ('parts', 'Contact', ('first_name', 'last_name', 'supplier'), ()),
    ('parts', 'Room', ('name', 'site'), ('site',)),
    ('qa', 'TestListInstance', ('user_key',), ('user_key',)),
]


def spec_constraint_name(spec):
    app_label, model_name, fields, _nullable = spec
    return constraint_name(apps.get_model(app_label, model_name), fields)


def constraints_by_name(model):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, model._meta.db_table)


def schema_drift(specs, started_with, present=None):
    """(added, removed): what a test changed, measured against what it started with.

    The classification the restoring teardown needs, kept out of it so that both
    directions can be asserted on an engine where neither actually happens - which is
    every engine but SQL Server. `present` is injectable for exactly that reason.
    """
    present = present or repair_constraint_present
    added = [s for s in specs if present(s) and spec_constraint_name(s) not in started_with]
    removed = [s for s in specs if not present(s) and spec_constraint_name(s) in started_with]
    return added, removed


def repair_constraint_present(spec):
    """Does the database already have the index this spec would create?

    By the repair's own generated name - which matters, because on SQL Server the
    4.0.2 migrations create exactly these names. A test that assumes a repair name
    can only have come from itself is wrong there, which is what the restoring
    teardown below exists for.
    """
    app_label, model_name, _fields, _nullable = spec
    return spec_constraint_name(spec) in constraints_by_name(apps.get_model(app_label, model_name))


class TestConstraintName(TestCase):

    def test_it_is_deterministic(self):
        """Idempotence and reversal both depend on this."""
        a = constraint_name(Contact, ('first_name', 'last_name', 'supplier'))
        b = constraint_name(Contact, ('first_name', 'last_name', 'supplier'))
        assert a == b

    def test_different_fields_give_different_names(self):
        assert constraint_name(Contact, ('first_name',)) != constraint_name(Contact, ('last_name',))

    def test_different_models_give_different_names(self):
        """The hash covers the table, so two models sharing a field list do not collide."""
        assert constraint_name(Contact, ('name',)) != constraint_name(Room, ('name',))

    def test_it_fits_every_backend_identifier_limit(self):
        """SQL Server allows 128; the shortest limit among supported backends is 30."""
        for model, fields in [
            (Contact, ('first_name', 'last_name', 'supplier')),
            (TestListInstance, ('user_key',)),
        ]:
            name = constraint_name(model, fields)
            assert len(name) <= 63, (name, len(name))


class TestBuiltConstraint(TestCase):

    def test_no_condition_when_nothing_is_nullable(self):
        c = _build(Contact, ('first_name', 'last_name', 'supplier'), ())
        assert c.condition is None

    def test_nullable_columns_produce_a_filtered_constraint(self):
        """Django permits many NULLs in a nullable unique column; SQL Server does not.

        Without the condition the restored index would reject a second NULL row that the
        application considers valid, so the filter is what makes the repair match
        Django's semantics rather than the engine's.
        """
        c = _build(Room, ('name', 'site'), ('site',))
        assert c.condition == Q(site__isnull=False)

    def test_every_nullable_column_appears_in_the_condition(self):
        c = _build(
            apps.get_model('service_log', 'Hours'),
            ('service_event', 'third_party', 'user'),
            ('third_party', 'user'),
        )
        assert c.condition == Q(third_party__isnull=False, user__isnull=False)


class TestSchemaDrift(TestCase):
    """The teardown's bookkeeping, asserted without needing an engine that drifts.

    Both faults this replaced are in here as cases: a constraint the test created and
    must take away, and one that was already there and must be put back. The second is
    the SQL Server case - the 4.0.2 migrations create indexes under these same generated
    names - and it cannot be produced on SQLite, so presence is injected.
    """

    def test_a_constraint_a_test_created_is_reported_as_added(self):
        added, removed = schema_drift(SPECS, started_with=set(), present=lambda spec: True)
        assert added == SPECS
        assert removed == []

    def test_a_constraint_that_was_already_there_is_left_alone(self):
        all_names = {spec_constraint_name(s) for s in SPECS}
        added, removed = schema_drift(SPECS, started_with=all_names, present=lambda spec: True)
        assert added == []
        assert removed == []

    def test_a_baseline_constraint_a_test_removed_is_reported_for_restoring(self):
        """The fault: a teardown that only removed would leave these gone for the rest
        of the run, because `TransactionTestCase` restores rows and not schema."""
        all_names = {spec_constraint_name(s) for s in SPECS}
        added, removed = schema_drift(SPECS, started_with=all_names, present=lambda spec: False)
        assert added == []
        assert removed == SPECS

    def test_nothing_to_do_when_nothing_moved(self):
        added, removed = schema_drift(SPECS, started_with=set(), present=lambda spec: False)
        assert (added, removed) == ([], [])


class TestRepairDecisions(TransactionTestCase):
    """`TransactionTestCase`, not `TestCase`.

    These open a schema editor, and SQLite refuses to do that inside an atomic block -
    which is what `TestCase` wraps every test in.

    **Schema has to be restored by hand here, in both directions.** On an engine that
    is genuinely missing a constraint the repair issues real DDL, so a test can leak
    one into the next - the fault the first version of this class had. The second
    version removed every repair-named constraint in `tearDown`, which has the opposite
    fault and a worse one: on SQL Server the 4.0.2 migrations create indexes under
    exactly these generated names, so a teardown that removed them stripped the test
    database of uniqueness the migrations had put back. `TransactionTestCase` truncates
    rows between tests and does not rebuild schema, so every test after it in that run
    would have been running without those constraints. @copilot found that on c#13.

    So each test records what was there when it started, and afterwards removes only
    what it added and puts back only what it took away.
    """

    def setUp(self):
        super().setUp()
        self.started_with = {spec_constraint_name(s) for s in SPECS if repair_constraint_present(s)}

    def tearDown(self):
        added, removed = schema_drift(SPECS, self.started_with)

        if added:
            with connection.schema_editor() as editor:
                remove_repaired_constraints(apps, editor, added)
        if removed:
            with connection.schema_editor() as editor:
                repair_unique_constraints(apps, editor, removed)
        super().tearDown()


    def test_it_does_nothing_where_the_database_already_enforces(self):
        """The whole basis for having no engine guard.

        On SQLite, PostgreSQL and MySQL every declared constraint is enforced, so every
        spec is skipped and no DDL is issued. This is the assertion that replaced
        `if connection.vendor != 'microsoft': return` - it tests the real condition
        rather than a proxy for it.
        """
        with connection.schema_editor() as editor:
            result = repair_unique_constraints(apps, editor, SPECS)

        if any(c in connection.vendor for c in ('sqlite', 'postgresql', 'mysql')):
            assert result['created'] == [], result
            assert len(result['already_enforced']) == len(SPECS), result
            assert result['blocked'] == [] and result['unsupported'] == [], result
        else:
            # An engine that may legitimately be missing them; every spec must still be
            # accounted for exactly once.
            total = sum(len(result[k]) for k in ('created', 'already_enforced', 'blocked', 'unsupported'))
            assert total == len(SPECS), result

    def test_a_partial_index_is_refused_where_unsupported_rather_than_emitted(self):
        """MySQL cannot express one, and must be told rather than left looking repaired."""
        if connection.features.supports_partial_indexes:
            self.skipTest("this engine supports partial indexes")

        with connection.schema_editor() as editor:
            result = repair_unique_constraints(apps, editor, SPECS)

        nullable_specs = [s for s in SPECS if s[3]]
        for spec in nullable_specs:
            label = "%s.%s %s" % (spec[0], spec[1], list(spec[2]))
            assert label in result['already_enforced'] + result['unsupported'], result

    def test_reversal_leaves_constraints_it_did_not_create(self):
        """Removal is by generated name, so the database's own indexes are untouched.

        Measured on the constraints the *database* named, not on every unique
        constraint: where the repair migrations have already run - SQL Server - a
        repair-named index is present and removing it is this function's documented
        job, so counting it here would assert the opposite of the behaviour.
        """
        before = self._unique_sets(Contact, owned_by_the_database=True)
        with connection.schema_editor() as editor:
            remove_repaired_constraints(apps, editor, SPECS)
        assert self._unique_sets(Contact, owned_by_the_database=True) == before

    def test_a_round_trip_returns_the_schema_to_where_it_started(self):
        """Both ways round, because the starting point depends on the engine.

        Where the constraint is missing the trip is repair-then-remove; where it is
        already there under the repair's name - a SQL Server database the migrations
        have been applied to - it is remove-then-repair, which is the direction that
        actually exercises both halves. On SQLite, PostgreSQL and MySQL the constraint
        is enforced under Django's own name, so both halves are no-ops and the
        assertion is that they are.
        """
        contact_specs = [s for s in SPECS if s[1] == 'Contact']
        before = self._unique_sets(Contact)

        if repair_constraint_present(contact_specs[0]):
            first, second = remove_repaired_constraints, repair_unique_constraints
        else:
            first, second = repair_unique_constraints, remove_repaired_constraints

        with connection.schema_editor() as editor:
            first(apps, editor, contact_specs)
        with connection.schema_editor() as editor:
            second(apps, editor, contact_specs)

        assert self._unique_sets(Contact) == before

    def _unique_sets(self, model, owned_by_the_database=False):
        repair_names = {spec_constraint_name(s) for s in SPECS}
        return {
            frozenset(d['columns'])
            for name, d in constraints_by_name(model).items()
            if d.get('unique') and d.get('columns')
            and not (owned_by_the_database and name in repair_names)
        }
