import os
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register()
def check_media_folder_permissions(app_configs, **kwargs):
    errors = []
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    
    # Check if MEDIA_ROOT is configured and if the directory exists
    # This check is very likely unnecessary, since Django appears to recreate the folder on manage.py check, but it is here for completeness.

    if not media_root:
        errors.append(Error("The Media folder is not configured"))
        return errors
        
    media_root_path = Path(media_root)

    if not media_root_path.exists():
        errors.append(Error(f"The Media folder '{media_root}' does not exist"))
        return errors
    # End of redundant check    
    
    uploads_dirs = [
        media_root_path,
        media_root_path / 'uploads',
        media_root_path / 'uploads' / 'tmp',
    ]
    

    for directory in uploads_dirs:
        if directory.exists():
            if not directory.is_dir() or not os.access(directory, os.W_OK):
                errors.append(
                    Error(
                        f"The Django server process does not have write permissions to '{directory}'.",
                        hint=f"Check folder permissions. You may need to run `sudo chown -R www-data:www-data {media_root}` and `sudo chmod -R 775 {media_root}` (replace www-data with your web server user).",
                        id='qatrack.E001',
                    )
                )
            else:
                try:
                    fd, temp_path = tempfile.mkstemp(dir=str(directory))
                    os.close(fd)
                    Path(temp_path).unlink()
                except Exception as e:
                    errors.append(
                        Error(
                            f"The Django server process could not create a file in '{directory}': {e}",
                            hint="Check folder permissions and disk space.",
                            id='qatrack.E002',
                        )
                    )
        else:
            parent = directory.parent
            if parent.exists() and not os.access(parent, os.W_OK):
                errors.append(
                    Error(
                        f"The Django server process does not have write permissions to '{parent}' to create '{directory}'.",
                        hint=f"Check folder permissions. You may need to run `sudo chown -R www-data:www-data {media_root}`.",
                        id='qatrack.E001',
                    )
                )
    return errors


def _directives(fmt):
    """The strptime directives in ``fmt``, in the order they appear."""
    return re.findall(r'%(.)', fmt)


def order_is_ambiguous(fmt):
    """True if this format's day and month could be read either way round.

    Ambiguity needs two things: a numeric day *and* a numeric month, with
    neither preceded by the year. ``%d %b %Y`` is safe because the month is a
    name. ``%Y-%m-%d`` is safe because nothing anywhere writes year-day-month,
    so seeing the year first settles the rest.
    """
    directives = _directives(fmt)
    if 'd' not in directives or 'm' not in directives:
        return False

    for directive in directives:
        if directive in ('Y', 'y'):
            return False
        if directive in ('d', 'm'):
            return True
    return False


def _day_first(fmt):
    for directive in _directives(fmt):
        if directive == 'd':
            return True
        if directive == 'm':
            return False
    return False


@register()
def check_ambiguous_date_formats(app_configs, **kwargs):
    """Warn about all-numeric date formats that do not lead with the year.

    QATrack+ defaults to ISO 8601 and deliberately does not suggest
    day/month/year or month/day/year anywhere in its examples. The reason is
    not tidiness. 03/05/2026 is the 3rd of May to most of the world and March
    5th in the United States, the string carries nothing that distinguishes
    them, and the US convention is entrenched enough that both readings turn
    up in the same datasets.

    In most software that is an annoyance. In a clinical QA record it is a
    date on which a machine was or was not verified, read by people trained in
    different conventions and by regulators who were not in the room. The
    profession's own habit of writing dates unambiguously exists for that
    reason, and the software should not quietly make it harder.

    So this is a warning rather than an error: a site that has decided it
    knows its own data can carry on. It should be a decision though, not
    something discovered later from a record that was read as the wrong day.
    """
    settings_to_check = [
        ('QATRACK_DATE_FORMAT', [getattr(settings, 'QATRACK_DATE_FORMAT', None)]),
        ('QATRACK_DATETIME_FORMAT', [getattr(settings, 'QATRACK_DATETIME_FORMAT', None)]),
        ('QATRACK_EXTRA_DATE_INPUT_FORMATS', getattr(settings, 'QATRACK_EXTRA_DATE_INPUT_FORMATS', [])),
        ('QATRACK_EXTRA_DATETIME_INPUT_FORMATS', getattr(settings, 'QATRACK_EXTRA_DATETIME_INPUT_FORMATS', [])),
    ]

    ambiguous = []
    for name, formats in settings_to_check:
        for fmt in formats or []:
            if fmt and order_is_ambiguous(fmt):
                ambiguous.append((name, fmt))

    if not ambiguous:
        return []

    listed = ', '.join('%s in %s' % (fmt, name) for name, fmt in ambiguous)
    orders = {_day_first(fmt) for _, fmt in ambiguous}

    if len(orders) > 1:
        # Both orders accepted at once: the same string now has two possible
        # meanings and QATrack+ resolves it by whichever is configured for
        # display. That is defined behaviour, but it is not a safe thing to
        # rely on when the data came from somewhere else.
        return [
            Warning(
                "Both day/month and month/day date formats are configured (%s). A date "
                "like 03/05/2026 is accepted by both and will be read using whichever "
                "one is your display format, so the same text entered by two people can "
                "mean two different days." % listed,
                hint="Use the default ISO format (%Y-%m-%d), which cannot be read two "
                     "ways, or accept only one of the two numeric orders.",
                id='qatrack.W004',
            )
        ]

    return [
        Warning(
            "An ambiguous date format is configured (%s). 03/05/2026 is the 3rd of May "
            "in most of the world and March 5th in the United States, and nothing in "
            "the date itself says which - a QC record read by someone using the other "
            "convention is silently off by months." % listed,
            hint="QATrack+ defaults to ISO 8601 (%Y-%m-%d, or %Y/%m/%d) for this "
                 "reason. A month name (%d %b %Y) is also unambiguous. This is a "
                 "warning, not an error - set it deliberately if your site needs it.",
            id='qatrack.W004',
        )
    ]


@register()
def check_translation_catalogues(app_configs, **kwargs):
    """Warn when a committed .mo no longer matches the .po beside it.

    A Warning rather than an Error on purpose. System checks run before
    `migrate` unless --skip-checks is passed, and a site part-way through
    editing its own translations should not be locked out of its migrations
    for it.
    """
    from qatrack.qatrack_core.translation_catalogues import catalogue_problems

    try:
        problems = catalogue_problems()
    except Exception:  # noqa: BLE001
        # Deliberately broad. This runs during system checks, which run before
        # `migrate`, and the docstring above promises it will not lock a site out
        # of its migrations. `OSError` alone was not enough: a malformed .po can
        # raise from the parser, and `locale_root` can raise AttributeError if
        # PROJECT_ROOT is unset. A diagnostic that cannot report is worth less
        # than a `migrate` that cannot run.
        return []

    return [
        Warning(
            problem,
            hint=(
                "The .po is what translators edit; the .mo is what Django reads. "
                "Recompile so the two agree."
            ),
            id='qatrack.W010',
        )
        for problem in problems
    ]


def declared_unique_columns(model):
    """Column sets the model says must be unique, as frozensets.

    Frozensets rather than tuples because uniqueness over (a, b) and (b, a) is
    the same guarantee, while introspection reports whatever order the index
    happens to use.

    The primary key is excluded: it is unique by construction and a missing one
    would fail far louder than this check.

    Conditional and expression-based UniqueConstraints are skipped. They are
    partial or functional indexes, and deciding whether the database's version
    matches the model's is a different and much harder comparison than "are
    these columns covered".
    """
    from django.db.models import UniqueConstraint

    expected = set()

    for field in model._meta.local_fields:
        if field.unique and not field.primary_key:
            expected.add(frozenset([field.column]))

    for fields in model._meta.unique_together:
        expected.add(frozenset(model._meta.get_field(f).column for f in fields))

    for constraint in model._meta.constraints:
        if not isinstance(constraint, UniqueConstraint):
            continue
        if getattr(constraint, 'condition', None) or getattr(constraint, 'expressions', None):
            continue
        expected.add(frozenset(model._meta.get_field(f).column for f in constraint.fields))

    return expected


def enforced_unique_columns(connection, table):
    """Column sets the database actually enforces as unique, as frozensets."""
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)

    enforced = set()
    for details in constraints.values():
        if details.get('unique') and details.get('columns'):
            enforced.add(frozenset(details['columns']))
    return enforced


def unenforced_unique_columns(declared, enforced):
    """Which declared unique column sets the database does not enforce.

    Split out from the check so the comparison can be tested without a
    database. A wider unique constraint does not imply a narrower one, so this
    is a plain set difference and not a subset test: uniqueness over (a, b)
    permits duplicate a values.
    """
    return sorted(
        (sorted(columns) for columns in declared - enforced),
        key=lambda cols: (len(cols), cols),
    )


@register(Tags.database)
def check_unique_constraints_enforced(app_configs=None, databases=None, **kwargs):
    """Warn when a model declares uniqueness the database is not enforcing.

    This exists because `mssql-django` drops a unique index when an unrelated
    `AlterField` retypes a model's primary key, and never recreates it - which
    the 4.0 migrations do to every model. The result is silent: the ORM stops
    raising IntegrityError and accepts duplicates. QATrack+ relies on this for
    TestListInstance.user_key, whose stated job is to keep API submissions
    unique. Confirmed against mssql-django 1.7.3, 1.8.0 and 2.0.0; not
    reproducible on PostgreSQL or SQLite.

    **A Warning, deliberately, not an Error.** Checks run before `migrate`, and
    an Error would abort it - on exactly the installations that already have
    the problem. Telling somebody their database is missing a constraint while
    refusing to let them run the migration that would fix it is worse than the
    constraint being missing.

    Registered under Tags.database so it runs on `migrate` and on
    `check --database <alias>`, and costs nothing on every other management
    command. One consequence worth knowing: on a first `migrate` the tables do
    not exist yet, so nothing is reported until the next run.
    """
    if not databases:
        return []

    from django.apps import apps
    from django.db import connections
    from django.db.utils import DatabaseError

    problems = []

    for alias in databases:
        connection = connections[alias]

        # A database we cannot reach or introspect is not this check's
        # business - other checks report that, and a broken connection should
        # not turn into a confusing message about constraints.
        try:
            with connection.cursor() as cursor:
                existing_tables = set(connection.introspection.table_names(cursor))
        except (DatabaseError, OSError):
            continue

        for model in apps.get_models():
            meta = model._meta
            if meta.proxy or not meta.managed or meta.db_table not in existing_tables:
                continue

            declared = declared_unique_columns(model)
            if not declared:
                continue

            try:
                enforced = enforced_unique_columns(connection, meta.db_table)
            except (DatabaseError, NotImplementedError):
                continue

            for columns in unenforced_unique_columns(declared, enforced):
                problems.append(
                    Warning(
                        "%s.%s declares %s unique, but %s is not enforcing it."
                        % (
                            meta.app_label,
                            meta.object_name,
                            ', '.join(columns),
                            connection.vendor,
                        ),
                        hint=(
                            "Duplicate rows can be created that other database "
                            "backends would reject. On SQL Server this is caused by "
                            "mssql-django dropping the index when the 4.0 migrations "
                            "retype primary keys; it is present in every released "
                            "version as of 2026-09.\n\n"
                            "The 4.0.2 migrations re-create these, so if you are "
                            "upgrading there is nothing to do: this warning is printed "
                            "before migrations run, and the same `migrate` repairs it. "
                            "Run `manage.py check_unique_constraints` first to see "
                            "whether any duplicate rows would block that - an index it "
                            "cannot create is reported and skipped rather than failing "
                            "the upgrade.\n\n"
                            "To add it by hand instead:\n\n"
                            "    CREATE UNIQUE INDEX %s ON %s (%s)\n\n"
                            "on SQL Server add WHERE %s IS NOT NULL if the column is "
                            "nullable, since it treats NULLs as equal."
                            % (
                                '%s_%s_uniq' % (meta.db_table, '_'.join(columns)),
                                meta.db_table,
                                ', '.join(columns),
                                ' IS NOT NULL AND '.join(columns),
                            )
                        ),
                        obj=model,
                        id='qatrack.W011',
                    )
                )

    return problems


def procedure_uses_pyplot(source):
    """The names a calculation procedure uses to reach `matplotlib.pyplot`.

    Returned sorted, empty when it does not touch pyplot.

    Parsed rather than searched. A procedure is Python, and `grep` for "pyplot"
    finds it in a comment, in a docstring and in a string literal, none of which
    draw anything. A site with a warning it cannot act on learns to ignore
    warnings.

    Two routes, because both work here:

    * importing it - `import matplotlib.pyplot as plt`, or
      `from matplotlib import pyplot`;
    * reaching it through the module the calculation context already provides -
      `matplotlib.pyplot.plot(...)`, with no import at all, because
      DEFAULT_CALCULATION_CONTEXT hands procedures `matplotlib` whole.

    A syntax error is not this function's problem: it returns nothing and lets
    whatever reports broken procedures report it.
    """
    import ast

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'matplotlib.pyplot' or alias.name == 'pylab':
                    found.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == 'matplotlib':
                for alias in node.names:
                    if alias.name == 'pyplot':
                        found.add(alias.asname or 'pyplot')
            elif node.module == 'matplotlib.pyplot':
                found.add('matplotlib.pyplot')
        elif isinstance(node, ast.Attribute) and node.attr == 'pyplot':
            if isinstance(node.value, ast.Name) and node.value.id == 'matplotlib':
                found.add('matplotlib.pyplot')

    return sorted(found)


@register(Tags.database)
def check_calculation_procedures_use_pyplot(app_configs=None, databases=None, **kwargs):
    """Warn when a calculation procedure draws with pyplot.

    `matplotlib.pyplot` keeps its figures in module-level state, so two
    procedures plotting at once in one process share it. QATrack+ makes that
    worse rather than better: `clean_mpl` in `qa/views/perform.py` calls
    `plt.clf()` and `plt.close('all')` after a view that may have plotted, and
    both act on **every** figure in the process rather than this request's. The
    function's own docstring says pyplot is not threadsafe, and the
    `except KeyError` wrapped round it is commented as failing "when multiple
    uploads are being analyzed at same time" - which is this, already observed.

    **Whether it can happen depends on how the site serves requests, which this
    check cannot see.** A system check runs under `manage.py`, in its own
    process; nothing tells it what is serving. The shipped Linux and Docker
    deployments configure gunicorn with sync workers, one request per process,
    and are safe by that configuration rather than by anything in the code. The
    shipped Windows deployment runs CherryPy's thread pool and is not.

    So this reports the half it can establish - that the procedures are written
    the vulnerable way - and the hint tells the reader which deployment turns it
    into a fault. A Warning, never an Error: the site may be on a configuration
    where it cannot happen, and in any case nothing is repaired by refusing to
    let them migrate.

    The failure is not a crash. It is a plot saved against the wrong test, or an
    empty one, in a record a physicist will read as evidence.

    Registered under Tags.database like `qatrack.W011`, so it runs on `migrate`
    and on `check --database <alias>` and costs nothing on every other command.
    On a first `migrate` the tables do not exist yet, so nothing is reported
    until the next run.
    """
    if not databases:
        return []

    from django.apps import apps
    from django.db import connections
    from django.db.utils import DatabaseError

    try:
        Test = apps.get_model('qa', 'Test')
    except LookupError:  # pragma: no cover - qa is always installed
        return []

    offenders = []
    seen = set()

    for alias in databases:
        connection = connections[alias]

        # Unreachable or un-migrated is not this check's business, exactly as
        # for W011: other checks report a broken connection, and a fresh
        # install's first `migrate` must not be derailed by a diagnostic.
        try:
            with connection.cursor() as cursor:
                tables = set(connection.introspection.table_names(cursor))
        except (DatabaseError, OSError):
            continue

        if Test._meta.db_table not in tables:
            continue

        try:
            procedures = (
                Test.objects.using(alias)
                .exclude(calculation_procedure=None)
                .exclude(calculation_procedure='')
                .values_list('pk', 'name', 'calculation_procedure')
            )
            procedures = list(procedures)
        except DatabaseError:
            continue

        for pk, name, source in procedures:
            if pk in seen:
                continue
            names = procedure_uses_pyplot(source or '')
            if names:
                seen.add(pk)
                offenders.append((name, names))

    if not offenders:
        return []

    offenders.sort()
    shown = offenders[:10]
    listed = ', '.join('"%s" (%s)' % (name, ', '.join(names)) for name, names in shown)
    if len(offenders) > len(shown):
        listed += ', and %d more' % (len(offenders) - len(shown))

    return [
        Warning(
            "%d calculation procedure(s) draw with matplotlib.pyplot: %s. pyplot "
            "holds its figures in module-level state, so two procedures plotting "
            "at the same time in one process can take each other's figures - and "
            "QATrack+ clears every figure in the process after a plot, not just "
            "the one it made. The result is a plot saved against the wrong test, "
            "or an empty one." % (len(offenders), listed),
            hint=(
                "Rewrite them to use UTILS.get_figure(), which returns a figure "
                "with its own canvas and cannot be taken by another "
                "calculation:\n\n"
                "    fig = UTILS.get_figure()\n"
                "    ax = fig.add_subplot(111)\n"
                "    ax.plot(xs, ys)\n"
                "    UTILS.write_file('plot.png', fig)\n\n"
                "Whether this can bite you depends on how you serve QATrack+, "
                "which a system check cannot see. The shipped Windows deployment "
                "serves requests on a CherryPy thread pool and shares one "
                "process, so it is exposed. The shipped Linux and Docker "
                "deployments run gunicorn with sync workers, one request per "
                "process, and are not - but that is their current configuration "
                "rather than a guarantee, and adding threads or workers with "
                "threads would change it. This is a warning, not an error: "
                "nothing here stops you migrating."
            ),
            id='qatrack.W012',
        )
    ]
