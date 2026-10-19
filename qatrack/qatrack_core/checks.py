import getpass
import os
import re
import shlex
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


def _permissions_hint(media_root, host_hint):
    """How to fix an unwritable media tree, in terms of the deployment in use.

    `host_hint` is the advice for an ordinary install - the caller builds it,
    because it needs the resolved application user and shell-quoted paths.
    This function only decides whether that advice applies, because inside a
    container it does not: there the process is an unprivileged uid and the
    directory is a docker volume, so the fix is applied from the *host* to the
    volume rather than with a chown inside the container that cannot work.

    Upgrading a pre-existing Docker installation lands on exactly this error,
    with everything in the volume still owned by the root the old image ran as.
    """
    if os.getenv('USE_DOCKER', '0').strip().lower() in ('1', 'true', 'yes', 'on'):
        return (
            "This is a container, so fix the volume from the host: stop the stack and run "
            "`docker run --rm -v <project>_media-volume:/media alpine chown -R %s:%s /media` "
            "(or `sudo chown -R %s:%s <dir>` if you use a bind mount). The upgrade guide "
            "covers this." % (os.getuid(), os.getgid(), os.getuid(), os.getgid())
        )
    return host_hint


@register()
def check_media_folder_permissions(app_configs, **kwargs):
    errors = []

    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        errors.append(
            Warning(
                'Django system check is running as root (or with sudo). Directory write permission checks may not report actual permissions for the application user.',
                hint='Run `python manage.py check` as the local OS user for QATrack+ services.',
                id='qatrack.W001',
            )
        )

    media_root = getattr(settings, 'MEDIA_ROOT', None)

    # Check if MEDIA_ROOT is configured and if the directory exists
    # This check is very likely unnecessary, since Django appears to recreate the folder on manage.py check, but it is here for completeness.

    if not media_root:
        errors.append(Error('The Media folder is not configured', id='qatrack.E003'))
        return errors

    media_root_path = Path(media_root)

    if not media_root_path.exists():
        errors.append(Error(f"The Media folder '{media_root}' does not exist", id='qatrack.E004'))
        return errors
    # End of redundant check

    try:
        import pwd

        app_user = pwd.getpwuid(os.geteuid()).pw_name
    except (ImportError, KeyError, AttributeError):
        app_user = getpass.getuser()

    if app_user == 'root':
        # Deliberately not `$USER`: a root operator pasting the hint would expand it to
        # `root` and chown the media tree to root, making the failure worse. W001 tells
        # them to re-run as the service user; this placeholder cannot be expanded.
        app_user = '<qatrack-os-user>'

    # Quote the path so the commands survive a MEDIA_ROOT containing spaces.
    quoted_root = shlex.quote(str(media_root))

    perm_hint = (
        f'Check folder permissions. You may need to run `sudo chown -R {app_user}:www-data {quoted_root}`, '
        f'`sudo find {quoted_root} -type d -exec chmod 2775 {{}} +`, and '
        f'`sudo find {quoted_root} -type f -exec chmod 664 {{}} +`.'
    )

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
                        hint=_permissions_hint(media_root, perm_hint),
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
                            hint='Check folder permissions and disk space.',
                            id='qatrack.E002',
                        )
                    )
        else:
            parent = directory.parent
            if parent.exists() and not os.access(parent, os.W_OK):
                errors.append(
                    Error(
                        f"The Django server process does not have write permissions to '{parent}' to create '{directory}'.",
                        hint=_permissions_hint(media_root, perm_hint),
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


@register()
def check_pdf_renderer(app_configs, **kwargs):
    """Report an unusable PDF_RENDERER, and an opt-in that did not take.

    Both are configuration problems that otherwise surface one report at a
    time, in `logs/debug.log`, on the day somebody needs a PDF.
    """
    from qatrack.qatrack_core.utils import PDF_RENDERERS, pdf_renderer

    configured = str(getattr(settings, 'PDF_RENDERER', 'auto') or 'auto').strip().lower()
    allowed = ('auto',) + PDF_RENDERERS

    if configured not in allowed:
        # A Warning, not an Error, and crane's measurement on Windows Server
        # 2022 is why: `manage.py check` failing on this blocks `migrate` and
        # makes `manage.py qcluster` exit immediately, so a typo in a
        # presentational setting stops every scheduled report and notice -
        # while the web server carries on rendering reports perfectly well
        # through the fallback. The severity has to match what the code does,
        # and what the code does is fall back.
        return [
            Warning(
                "PDF_RENDERER is %r, which is not one of %s." % (
                    getattr(settings, 'PDF_RENDERER', None),
                    ", ".join(repr(value) for value in allowed),
                ),
                hint=(
                    "Reports will be rendered as though it were 'auto'. Set it in "
                    "qatrack/local_settings.py to one of the values above, or remove it."
                ),
                id='qatrack.W015',
            )
        ]

    if pdf_renderer() != 'weasyprint':
        return []

    try:
        import weasyprint  # noqa: F401
    except Exception as e:  # noqa: BLE001
        # Deliberately broad, and the reason this check earns its place: a
        # missing pango raises OSError from the import, not ImportError, so
        # the usual narrow catch would miss the case an administrator most
        # needs told about - they installed the libraries, and it did not take.
        return [
            Warning(
                "PDF_RENDERER selects WeasyPrint, but importing it fails: %s: %s" % (
                    type(e).__name__, e,
                ),
                hint=(
                    "Every report will be rendered by Chrome instead. On Windows, "
                    "WeasyPrint needs the pango libraries from MSYS2 - see the Windows "
                    "install guide. Check with `python -m weasyprint --info`."
                ),
                id='qatrack.W016',
            )
        ]

    return []
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


def configured_cache_tables():
    """(alias, table) for every configured database cache, by backend type.

    Type, not dotted path: a subclass of Django's database cache under another
    module name is still a database cache, and a `BACKEND.endswith(...)` test
    misses it. Mirrors `createcachetable`.
    """
    from django.core.cache import caches
    from django.core.cache.backends.db import BaseDatabaseCache

    found = []
    for alias in getattr(settings, 'CACHES', {}):
        try:
            cache = caches[alias]
        except Exception:  # noqa: BLE001 - a broken backend is W014's problem, not this one
            continue
        if isinstance(cache, BaseDatabaseCache):
            table = getattr(cache, '_table', None)
            if table:
                found.append((alias, table))
    return found


@register(Tags.caches, Tags.database, deploy=False)
def check_cache_tables_exist(app_configs=None, databases=None, **kwargs):
    """Every configured database cache must have its table.

    `qatrack_core.0002_cache_table` creates them during `migrate`, and there are
    three situations it cannot cover:

    - **A routed cache.** `createcachetable` consults
      `router.allow_migrate_model`. A router that puts the cache table on a
      dedicated cache database while denying `qatrack_core` there leaves the
      migration running only where the table is unwanted. A migration runs where
      its own app is migrated; it cannot reach the other database.
    - **A backend the migration did not recognise**, on an installation that
      migrated before this check existed.
    - **A site that never ran `createcachetable` and never re-migrated.**

    The symptom without this is not subtle but it is badly timed: every write
    that invalidates a cached count issues a DELETE against the table from a
    `post_save` receiver, so creating a user raises `OperationalError: no such
    table`. `manage.py check` passed on such a database until now, which is what
    made it a surprise during an upgrade rather than before one.

    A warning, not an error: the site runs until something writes, and failing
    `migrate` outright over a cache table would be worse than saying so.
    """
    if not databases:
        return []

    # Imported here, as the other database checks in this module do, so importing
    # checks.py does not pull the database layer in at settings-load time.
    from django.core.cache.backends.db import BaseDatabaseCache
    from django.db import connections, router
    from django.db.utils import DatabaseError

    problems = []
    for alias in databases:
        connection = connections[alias]
        try:
            with connection.cursor() as cursor:
                existing = set(connection.introspection.table_names(cursor))
        except (DatabaseError, OSError):
            # Unreachable or un-migrated is not this check's business, exactly as
            # for W011 and W012.
            continue

        for cache_alias, table in configured_cache_tables():
            if table in existing:
                continue
            if not router.allow_migrate_model(alias, BaseDatabaseCache(table, {}).cache_model_class):
                # The router says this table does not belong on this database.
                continue
            problems.append(
                Warning(
                    "The cache table %r for CACHES[%r] is missing from the %r database."
                    % (table, cache_alias, alias),
                    hint=(
                        "Run `manage.py migrate` - qatrack_core.0002_cache_table "
                        "creates it - or `manage.py createcachetable %s --database %s` "
                        "if a database router keeps that table off the application "
                        "database.\n\n"
                        "Until it exists, any write that invalidates a cached count "
                        "fails: creating a user raises `no such table`." % (table, alias)
                    ),
                    id='qatrack.W013',
                )
            )
    return problems

