# TODO(5.0): revisit the settings architecture as a whole.
#
# The checks in this module are deliberately the cheap version of a bigger
# question - whether QATrack+ should move to a validated settings layer
# (pydantic-settings) instead of `from .local_settings import *`. They are
# also the experiment that answers it:
#
#   - If silent-configuration bugs stop turning up, the larger move was never
#     needed and this TODO can be closed.
#   - If they keep turning up in forms a check cannot express - cross-field
#     constraints, conditionally-required settings, type coercion - that is
#     concrete evidence for the move rather than a guess.
#
# 5.0 is the place to act on it: that release already carries the Django 5.2
# LTS upgrade, so it is the natural boundary for a breaking configuration
# change. Note the README commits to X.Y -> (X+3).0 upgrade paths, so any
# change of format has to keep existing hand-edited local_settings.py files
# working, or ship a shim that does.
#
# Rationale and the options considered are in AGENTS.md, "Adding a setting".
#
# Two naming inconsistencies are also parked until then, because renaming a
# setting breaks every local_settings.py that sets it, and 5.0 is the only
# place that is acceptable:
#
#   1. The clean-username family. Four names, three prefix conventions, and two
#      of them bound to the same value in settings.py:
#
#          ACCOUNTS_CLEAN_USERNAME          callable
#          AD_CLEAN_USERNAME                callable
#          ACCOUNTS_CLEAN_USERNAME_STRING = AD_CLEAN_USERNAME_STRING = ''
#
#      The aliasing is why two backends call .replace() twice with what is
#      usually the same value (see accounts/backends.py). Collapsing this to
#      one pair - a callable and a string, with one prefix - is the fix, but it
#      touches AD deployments, and AD/LDAP is the area of the codebase with no
#      test coverage at all. Do not attempt it without a way to test LDAP.
#
#   2. Boolean naming. QATrack+'s own flags are USE_ADFS, USE_ISSUES and
#      USE_SQL_REPORTS, against a single EMAIL_ENABLED. USE_* is the majority,
#      so EMAIL_ENABLED is the outlier - but it appears in five deploy examples
#      and two documentation pages, and W001 above already steers deployers
#      toward it. Renaming it is a 5.0 job; renaming the USE_* settings to
#      match it would be moving three names to suit one.

import os
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


@register()
def check_deprecated_email_notification_settings(app_configs, **kwargs):
    # EMAIL_NOTIFICATION_USER/PWD were replaced by the standard Django
    # EMAIL_HOST_USER/EMAIL_HOST_PASSWORD settings. settings.py still copies
    # them over for anyone upgrading from an older local_settings.py, but
    # that shim is silent - this check gives upgrading deployers a visible
    # nudge to switch over rather than leaving them on a deprecated path
    # indefinitely.
    warnings = []
    if getattr(settings, 'EMAIL_NOTIFICATION_USER', None) or getattr(settings, 'EMAIL_NOTIFICATION_PWD', None):
        warnings.append(
            Warning(
                "EMAIL_NOTIFICATION_USER/EMAIL_NOTIFICATION_PWD are deprecated.",
                hint="Rename these to EMAIL_HOST_USER/EMAIL_HOST_PASSWORD in your local_settings.py.",
                id='qatrack.W001',
            )
        )
    return warnings


# Placeholder values shipped in the deploy/*/local_settings.py templates. If any
# of these survive into a running instance, the template was copied but not
# finished.
_HOST_PLACEHOLDERS = ('XX.XXX.XXX.XX', 'YOUR_HOST_NAME_HERE')
_SECRET_PLACEHOLDERS = ('your_password_here', 'qatrackpass', 'change_me')


@register()
def check_unedited_placeholders(app_configs, **kwargs):
    """Catch deploy templates that were copied but never filled in.

    `import *` means an unedited placeholder is indistinguishable from a
    deliberate value - nothing validates it, and ALLOWED_HOSTS = ['XX.XXX.XXX.XX']
    fails at request time with a confusing DisallowedHost rather than at
    startup with something actionable.
    """
    problems = []

    for name in ('ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS'):
        values = getattr(settings, name, None) or []
        stale = [v for v in values if any(p in str(v) for p in _HOST_PLACEHOLDERS)]
        if stale:
            problems.append(
                Error(
                    "%s still contains the placeholder(s) shipped in the "
                    "deploy template: %s" % (name, ', '.join(repr(s) for s in stale)),
                    hint="Replace them with your server's host name or IP address "
                         "in qatrack/local_settings.py.",
                    id='qatrack.E002',
                )
            )

    # Credentials are a warning rather than an error: they are documented
    # example values, so an instance using them runs fine - it is just
    # using a password published in this repository.
    used = set()
    for db in (getattr(settings, 'DATABASES', None) or {}).values():
        pwd = str(db.get('PASSWORD', ''))
        used.update(p for p in _SECRET_PLACEHOLDERS if p and p == pwd)
    # Only when email is actually turned on: the templates ship
    # EMAIL_HOST_PASSWORD = 'your_password_here' commented-out alongside the
    # rest of the email block, and an instance with EMAIL_ENABLED off is not
    # using it for anything. Flagging it there would be noise.
    if getattr(settings, 'EMAIL_ENABLED', False):
        email_pwd = str(getattr(settings, 'EMAIL_HOST_PASSWORD', '') or '')
        used.update(p for p in _SECRET_PLACEHOLDERS if p and p == email_pwd)

    if used and not getattr(settings, 'DEBUG', False):
        problems.append(
            Warning(
                "A documented example password is in use: %s" % ', '.join(sorted(used)),
                hint="These values are published in this repository and in the "
                     "deploy/*/create_db_and_role.sql scripts. Change them to "
                     "something unique to your organization before clinical use.",
                id='qatrack.W002',
            )
        )

    return problems


def _suspect_setting_names(defined, known, cutoff=0.85):
    """Return [(defined_name, suggestion), ...] for probable typos.

    Split out from the check below so it can be tested without importing a
    real local_settings.py.

    Only names with a *close* match are reported. A deployer is free to define
    their own helper constants in local_settings.py, and those have no near
    neighbour among the real settings, so they stay silent. The cutoff is
    deliberately high - the goal is catching TIMEZONE for TIME_ZONE, not
    second-guessing anyone.
    """
    import difflib

    suspects = []
    for name in sorted(defined):
        if name in known:
            continue
        close = difflib.get_close_matches(name, known, n=1, cutoff=cutoff)
        if close:
            suspects.append((name, close[0]))
    return suspects


@register()
def check_local_settings_typos(app_configs, **kwargs):
    """Warn about names in local_settings.py that look like misspelt settings.

    `from .local_settings import *` silently accepts anything. Writing
    TIMEZONE instead of TIME_ZONE defines a new, unused name and leaves the
    real setting at its default - no error, no warning, and the symptom shows
    up much later as "why is my timezone wrong". Nothing else in the stack can
    catch this, because by the time settings are loaded the misspelling is
    indistinguishable from a deliberate constant.
    """
    try:
        from qatrack import local_settings
    except ModuleNotFoundError:
        # Absent under Docker (settings.py configures itself from the
        # environment and never imports it) and on a bare test run.
        return []

    from django.conf import global_settings

    from qatrack import settings as qatrack_settings

    known = {n for n in dir(global_settings) if n.isupper()}
    known |= {n for n in dir(qatrack_settings) if n.isupper()}
    defined = {n for n in dir(local_settings) if n.isupper()}

    return [
        Warning(
            "local_settings.py defines %s, which is not a QATrack+ or Django setting." % name,
            hint="Did you mean %s? If %s is your own constant, you can ignore this." % (
                suggestion, name),
            id='qatrack.W003',
        )
        for name, suggestion in _suspect_setting_names(defined, known)
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
                            "version as of 2026-09. Until a repair migration ships, "
                            "recreate it by hand:\n\n"
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
