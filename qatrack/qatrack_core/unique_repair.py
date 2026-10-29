"""Make the database enforce the uniqueness the models declare.

Some backends silently stop enforcing a unique constraint. `mssql-django` drops a
unique index when an unrelated `AlterField` retypes a model's primary key and never
recreates it, and the 4.0 migrations do that to every model - so a SQL Server
installation accepts duplicates the ORM believes are impossible, with no
`IntegrityError` and nothing in a log. `qatrack.W014` reports which constraints are
affected; `manage.py check_unique_constraints` reports the rows that block repairing
them.

**This module names no database engine.** An earlier version guarded on
`connection.vendor == 'microsoft'`, which was a proxy for "this engine has the bug" -
a statement about today's `mssql-django` rather than about the database in front of
it. Instead, each constraint is repaired only if the database is *not currently
enforcing it*, which is the real condition. On an engine that enforces what it is
told, every constraint is skipped and this does nothing; measured on SQLite,
PostgreSQL 15 and MySQL 8, all three report nothing to repair. If another backend ever
develops the same fault, this fixes it without being changed.

**Django generates the SQL, not this module.** `schema_editor.add_constraint` with a
`UniqueConstraint` lets each backend emit its own syntax, including the `WHERE ... IS
NOT NULL` that a nullable column needs on SQL Server - where NULLs are treated as
equal, unlike every other engine here. It also degrades correctly: Django returns no
SQL at all where `supports_partial_indexes` is False (MySQL), rather than this module
emitting something invalid.

**It changes no migration state.** The models already declare this uniqueness and the
migration graph already records it - the database is what diverged. So the callers are
`RunPython` with no `state_operations`, and running them cannot make `makemigrations`
report a change.

**It skips rather than fails.** A site may already hold rows that violate a constraint
nothing was enforcing. Creating the index would fail, and failing here aborts the
upgrade for exactly the installations that most need it.
"""

import hashlib

from django.db import DEFAULT_DB_ALIAS
from django.db.models import Count, Q, UniqueConstraint


def constraint_name(model, fields):
    """A deterministic name, short enough for any backend's identifier limit.

    Deterministic because it is what makes `repair_unique_constraints` idempotent and
    lets `remove_repaired_constraints` find only what this created - never an index the
    database had of its own.
    """
    table = model._meta.db_table
    digest = hashlib.sha1(("%s:%s" % (table, ",".join(fields))).encode()).hexdigest()[:8]
    return "qatrack_uniq_%s_%s" % (table[:40], digest)


def _build(model, fields, nullable=None):
    """The constraint to add: filtered when any of its columns may be NULL.

    The condition is what makes this match Django's semantics rather than SQL Server's.
    Django permits many NULLs in a nullable unique column - standard SQL treats them as
    distinct - so an unfiltered unique index would reject a second NULL row that the
    application considers perfectly valid.
    """
    if nullable is None:
        nullable = nullable_fields(model, fields)
    condition = Q(**{"%s__isnull" % f: False for f in nullable}) if nullable else None
    return UniqueConstraint(
        fields=list(fields),
        name=constraint_name(model, fields),
        condition=condition,
    )


def _columns(model, fields):
    return frozenset(model._meta.get_field(f).column for f in fields)


def _is_enforced(connection, model, fields):
    """Whether some unique index already covers exactly these columns.

    **It cannot tell a full index from a filtered one, and Django will not help.**
    `get_constraints()` returns the same dict for
    `CREATE UNIQUE INDEX ... (b)` and `CREATE UNIQUE INDEX ... (b) WHERE b IS NOT NULL` -
    measured: identical keys, `unique=True`, no predicate anywhere. So an index that
    excludes some rows reads as enforcing, and the repair skips a column set that is
    still open to duplicates among the excluded rows.

    That matters less than it sounds for the case this repair exists for - the filtered
    indexes in play are the ones *this* code creates for nullable columns, and matching
    them is correct - but it is a real gap for an index somebody else filtered, and it
    is not closable here: comparing predicates needs backend-specific SQL
    (`sqlite_master.sql`, `pg_index.indpred`, `sys.indexes.filter_definition`).

    What closes it instead is evidence rather than introspection:
    `manage.py check_unique_constraints --verify-enforced` looks for duplicate rows in
    the column sets this reports as enforced, which is the symptom a filtered index
    would produce. Raised by @coderabbitai on c#5 as a heavy lift; this is the part that
    is not.
    """
    # One introspection, shared with `qatrack.W011` and
    # `manage.py check_unique_constraints`, so the three cannot drift apart on
    # what "enforced" means. Imported here rather than at module scope because
    # migrations import this module and `checks.py` pulls in app registry state.
    from qatrack.qatrack_core.checks import enforced_unique_columns

    return _columns(model, fields) in enforced_unique_columns(
        connection, model._meta.db_table
    )


def nullable_fields(model, fields):
    """Which of `fields` the model permits NULL in.

    Asked of the model rather than written down beside each constraint. Sixteen
    specs used to carry a hand-maintained tuple of nullable field names, and
    nothing checked it against the model - so a field made nullable later, or a
    seventeenth spec written in a hurry, would have silently changed which rows
    count as duplicates. In a migration `model` is the historical one, so this
    is the nullability as of that migration, which is what the index being built
    has to match.
    """
    return tuple(f for f in fields if model._meta.get_field(f).null)


def duplicate_groups(model, fields, using=None):
    """Groups of rows sharing a value for `fields`, NULLs excluded.

    One implementation, shared by the repair and by
    `manage.py check_unique_constraints`, because the command's verdict is only
    worth anything if it is answering the same question the migration will ask.
    They were two functions that excluded NULLs differently - the repair for the
    nullable fields only, the command for every field - so the command could
    report "no duplicates" where the repair would find a blocker. No spec in
    tree triggered it, which is the only reason it was not a live defect.

    NULLs are excluded because the index that matches Django's intent is a
    filtered one: Django permits many NULLs in a nullable unique column where
    standard SQL treats them as distinct, so a row with a NULL is not a
    duplicate and counting those groups would report rows the repair ignores.

    `using` is not optional in practice. Without it this reads the default - or
    routed - database while the schema is introspected from `--database`, so a
    caller could report one database's indexes against another's rows and look
    entirely consistent doing it. `_default_manager` rather than `objects`,
    because a model is not obliged to call it that.
    """
    qs = model._default_manager.using(using or DEFAULT_DB_ALIAS)
    for f in nullable_fields(model, fields):
        qs = qs.exclude(**{"%s__isnull" % f: True})
    return (
        qs.values(*fields)
        .annotate(num=Count("pk"))
        .filter(num__gt=1)
        .order_by("-num")
    )


def repair_unique_constraints(apps, schema_editor, specs, log=None):
    """Add a unique constraint for each spec the database is not enforcing.

    `specs` is a sequence of (app_label, model_name, field_names); which of those
    fields may be NULL is asked of the model rather than written down.
    Returns counts so a caller - or a test - can assert on what happened rather than
    parsing output.
    """
    connection = schema_editor.connection
    result = {"created": [], "already_enforced": [], "blocked": [], "unsupported": []}

    def say(message):
        if log is not None:
            log(message)

    for app_label, model_name, fields in specs:
        model = apps.get_model(app_label, model_name)
        nullable = nullable_fields(model, fields)
        label = "%s.%s %s" % (app_label, model_name, list(fields))

        if _is_enforced(connection, model, fields):
            result["already_enforced"].append(label)
            continue

        if nullable and not connection.features.supports_partial_indexes:
            # Django would emit nothing here. Say so rather than letting it look repaired.
            result["unsupported"].append(label)
            say("  %s: not repaired - %s cannot express a partial unique index"
                % (label, connection.vendor))
            continue

        duplicates = duplicate_groups(model, fields, using=connection.alias).count()
        if duplicates:
            result["blocked"].append((label, duplicates))
            say(
                "  %s: NOT repaired - %d duplicated value(s) already present. This "
                "migration records as applied either way and will not retry, so "
                "`qatrack.W011` will keep reporting this column set until it is "
                "resolved: run `manage.py check_unique_constraints` to list the "
                "duplicates, resolve them, then add the index with the CREATE UNIQUE "
                "INDEX statement that check prints." % (label, duplicates)
            )
            continue

        schema_editor.add_constraint(model, _build(model, fields, nullable))
        result["created"].append(label)
        say("  %s: unique constraint restored%s"
            % (label, " (NULLs excluded)" if nullable else ""))

    return result


def remove_repaired_constraints(apps, schema_editor, specs):
    """Reverse of `repair_unique_constraints`: remove the names this module owns.

    Keyed on the generated name, so a constraint the database had of its own is left
    alone. A name that is not present is not an error - the forward pass skips
    constraints that were already enforced, so there is nothing to remove for those.

    **It removes by name, not by what a particular call created,** and the two are
    not the same thing. On a database where an earlier run of the repair *migration*
    created the constraint, a later forward pass reports `already_enforced` and adds
    nothing, yet this still removes the index, because the name is there. That is
    correct for the only caller - a migration reversing its own forward pass - and it
    is why calling forward then reverse is not an identity on such a database.
    Measured on SQL Server 2022, where the 4.0 retype drops
    `parts.Contact (first_name, last_name, supplier_id)` and the 4.0.2 repair
    migration re-creates it under the generated name.
    """
    connection = schema_editor.connection
    for app_label, model_name, fields in specs:
        model = apps.get_model(app_label, model_name)
        name = constraint_name(model, fields)
        with connection.cursor() as cursor:
            existing = connection.introspection.get_constraints(
                cursor, model._meta.db_table
            )
        if name in existing:
            schema_editor.remove_constraint(model, _build(model, fields))
