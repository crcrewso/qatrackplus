"""Find the rows that would block re-creating a missing unique index.

`qatrack.W011` reports *that* the database is not enforcing uniqueness a model
declares. This reports *why it cannot simply be re-added*: the rows already there
that violate it.

Separate from the check, and a command rather than a second check, for the same
reason `check_translations` is: checks run on every `migrate` and on
`manage.py check`, and scanning tables for duplicates is too expensive to do
there. This is run deliberately, before the repair migration.
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Count

from qatrack.qatrack_core.checks import (
    declared_unique_columns,
    enforced_unique_columns,
    unenforced_unique_columns,
)


def fields_for_columns(model, columns):
    """Map database column names back to field names, for ORM queries.

    Returns None if any column cannot be mapped, so the caller can report the
    column set rather than silently scanning the wrong thing.
    """
    by_column = {f.column: f.name for f in model._meta.local_fields}
    try:
        return [by_column[c] for c in columns]
    except KeyError:
        return None


def duplicate_groups(model, field_names, using=DEFAULT_DB_ALIAS):
    """Groups of rows sharing a value for `field_names`, NULLs excluded.

    NULLs are excluded deliberately, because that is what the index this is
    validating will do. Django's `unique=True` on a nullable column permits many
    NULLs - standard SQL treats them as distinct - so the index that matches the
    model's intent is a filtered one, and a row with a NULL is not a duplicate.
    Counting NULL groups here would report rows the repair does not care about.

    `using` is not optional in practice. Without it this read the default - or routed -
    database while the schema was introspected from `--database`, so the command could
    report one database's indexes against another's rows and look entirely consistent
    doing it. `_default_manager` rather than `objects`, because a model is not obliged
    to call it that.
    """
    qs = model._default_manager.using(using)
    for name in field_names:
        qs = qs.exclude(**{"%s__isnull" % name: True})
    return (
        qs.values(*field_names)
        .annotate(num=Count("pk"))
        .filter(num__gt=1)
        .order_by("-num")
    )


def summarise_groups(groups, limit):
    """Walk the groups once, keeping only `limit` of them.

    `list(groups)` defeats `--limit` for the thing that actually hurts: a badly
    affected production table can have millions of duplicated values, and all of them
    were transferred and held in memory so that twenty could be printed. Counts stay
    complete because they are accumulated as we go.

    Returns (kept, total_groups, excess_rows).
    """
    kept = []
    total = 0
    excess = 0
    for group in groups.iterator():
        total += 1
        excess += group["num"] - 1
        if len(kept) < limit:
            kept.append(group)
    return kept, total, excess


class Command(BaseCommand):
    help = "Report rows that would block re-creating a unique index the database has lost"

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to inspect (default: default).",
        )
        parser.add_argument(
            "--verify-enforced",
            action="store_true",
            help=(
                "Also look for duplicates in the column sets this database reports as "
                "already enforced. Slower - it scans those tables too - but it is the "
                "only way to catch a *filtered* unique index, which introspection "
                "cannot distinguish from a full one."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Most duplicate groups to list per model (default: 20). Counts are always complete.",
        )

    def handle(self, *args, **options):
        connection = connections[options["database"]]
        limit = options["limit"]

        self.stdout.write("Database: %s (%s)" % (options["database"], connection.vendor))

        checked = 0
        unenforced_total = 0
        blocked = []
        uninspectable = []
        contradictory = []

        for model in apps.get_models():
            # Proxy and unmanaged models are both skipped, matching the system check
            # in checks.py. A proxy shares its concrete model's table and declared
            # fields, so without this every unenforced set on that table was reported
            # a second time under the proxy's name.
            if not model._meta.managed or model._meta.proxy:
                continue
            declared = declared_unique_columns(model)
            if not declared:
                continue
            checked += 1
            try:
                enforced = enforced_unique_columns(connection, model._meta.db_table)
            except Exception as e:  # noqa: BLE001 - a missing table is not this command's problem
                uninspectable.append(model._meta.label)
                self.stdout.write(
                    self.style.WARNING("  %s: could not introspect %s (%s)" % (
                        model._meta.label, model._meta.db_table, e))
                )
                continue

            if options["verify_enforced"]:
                # Django's introspection returns the same thing for a full unique index
                # and a filtered one, so a column set reported as enforced may still
                # permit duplicates among the rows the filter excludes. Predicates are
                # not reachable through the ORM; duplicate rows are the symptom, and a
                # symptom is checkable.
                for columns in sorted(declared & enforced, key=sorted):
                    field_names = fields_for_columns(model, columns)
                    if field_names is None:
                        continue
                    _, total_groups, excess = summarise_groups(
                        duplicate_groups(model, field_names, using=options["database"]),
                        limit,
                    )
                    if total_groups:
                        contradictory.append(
                            (model._meta.label, columns, total_groups, excess))
                        self.stdout.write(self.style.ERROR(
                            "  BAD  %s %s - reported as enforced, yet %d duplicated "
                            "value%s present. The index is probably filtered."
                            % (model._meta.label, columns, total_groups,
                               "" if total_groups == 1 else "s")
                        ))

            for columns in unenforced_unique_columns(declared, enforced):
                unenforced_total += 1
                field_names = fields_for_columns(model, columns)
                if field_names is None:
                    self.stdout.write(self.style.WARNING(
                        "  %s %s: cannot map these columns to fields; check by hand"
                        % (model._meta.label, columns)
                    ))
                    continue

                shown, total_groups, excess = summarise_groups(
                    duplicate_groups(model, field_names, using=options["database"]), limit
                )
                if not total_groups:
                    self.stdout.write(self.style.SUCCESS(
                        "  OK   %s %s - not enforced, no duplicates" % (model._meta.label, columns)
                    ))
                    continue

                blocked.append((model._meta.label, columns, total_groups, excess))
                self.stdout.write(self.style.ERROR(
                    "  DUPS %s %s - %d duplicated value%s, %d row%s to resolve"
                    % (model._meta.label, columns, total_groups,
                       "" if total_groups == 1 else "s", excess, "" if excess == 1 else "s")
                ))
                for g in shown:
                    values = ", ".join("%s=%r" % (n, g[n]) for n in field_names)
                    self.stdout.write("         %s (%d rows)" % (values, g["num"]))
                if total_groups > len(shown):
                    self.stdout.write("         ... and %d more" % (total_groups - len(shown)))

        self.stdout.write("")
        self.stdout.write("%d models declare uniqueness; %d column set%s not enforced by this database."
                          % (checked, unenforced_total, "" if unenforced_total == 1 else "s"))

        if contradictory:
            self.stdout.write(self.style.ERROR(
                "%d column set%s reported as enforced but contain duplicates. An index "
                "covering those columns exists, so the repair migration will skip them, "
                "and it is almost certainly filtered - check its definition in the "
                "database and re-create it unfiltered once the rows are resolved."
                % (len(contradictory), "" if len(contradictory) == 1 else "s")
            ))

        if uninspectable:
            # Saying "everything is enforced" after failing to look at some of it is
            # the one answer this command must never give: it is indistinguishable
            # from a clean result and would send a site into the repair migration
            # believing there is nothing to do.
            self.stdout.write(self.style.WARNING(
                "Inconclusive: %d model%s could not be introspected (%s). Resolve those "
                "before relying on this result - a constraint missing on a table that "
                "could not be read would not appear above."
                % (len(uninspectable), "" if len(uninspectable) == 1 else "s",
                   ", ".join(sorted(uninspectable)))
            ))

        if not unenforced_total:
            if uninspectable:
                self.stdout.write(
                    "Nothing to repair among the models that could be read."
                )
            elif contradictory:
                self.stdout.write(
                    "Nothing missing, but see the contradictions above."
                )
            else:
                self.stdout.write(self.style.SUCCESS(
                    "Nothing to repair - every declared unique constraint is enforced here."
                ))
            return

        if blocked:
            self.stdout.write(self.style.ERROR(
                "%d of them cannot be re-added until the rows above are resolved." % len(blocked)
            ))
            self.stdout.write(
                "Resolve each by deciding which row is correct and changing or deleting the others, "
                "then run this again. The repair migration skips an index it cannot create and says so, "
                "so it will not fail the upgrade - but the constraint stays unenforced until this is clear."
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                "No duplicates - the repair migration can re-create every one of them."
            ))
