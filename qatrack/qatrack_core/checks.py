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

    **It is not a report about stored data, and the wording must not read like
    one.** Dates live in `DateField` and `DateTimeField` columns, so every date
    already in the database means exactly one day; there is nothing ambiguous
    to repair and this setting does not alter any of it. The exposure is at the
    boundary - what a person types and what a page shows - which is why the
    hint says so first. An upgrading site reading a warning as "your records
    may be wrong" would be being frightened by a warning about a setting.

    An upgrade also does not raise this by itself: the shipped default is ISO,
    which is unambiguous, so the check is silent unless somebody has chosen a
    numeric day/month format.
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
                hint="Nothing already saved is affected: QATrack+ stores dates as "
                     "dates, not as text. This is about what is typed in from now on.\n\n"
                     "Use the default ISO format (%Y-%m-%d), which cannot be read two "
                     "ways, or accept only one of the two numeric orders.",
                id='qatrack.W004',
            )
        ]

    return [
        Warning(
            "An ambiguous date format is configured (%s). 03/05/2026 is the 3rd of May "
            "in most of the world and March 5th in the United States, and nothing in "
            "the date itself says which, so someone typing or reading a date can mean "
            "a different day from the one QATrack+ records." % listed,
            hint="Nothing already saved is affected: QATrack+ stores dates as dates, "
                 "not as text, so every date in your database means exactly one day "
                 "and this setting does not change any of them. It affects only what "
                 "is typed in and shown from now on.\n\n"
                 "You are seeing this because a numeric day/month format is set; the "
                 "shipped default, ISO 8601 (%Y-%m-%d), does not raise it, and a month "
                 "name (%d %b %Y) is unambiguous too. This is a warning, not an error "
                 "- keep your format if your site wants it.",
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


def procedure_uses_pyplot(source):
    """The names a calculation procedure uses to reach `matplotlib.pyplot`.

    Returned sorted, empty when it does not touch pyplot.

    Parsed rather than searched. A procedure is Python, and `grep` for "pyplot"
    finds it in a comment, in a docstring and in a string literal, none of which
    draw anything. A site with a warning it cannot act on learns to ignore
    warnings.

    Every route that reaches the same module state counts, which nsmela's review
    of q#904 showed is more than the two obvious ones:

    * importing pyplot - `import matplotlib.pyplot as plt`, or
      `from matplotlib import pyplot`, or `from matplotlib.pyplot import plot`;
    * importing `pylab`, which is pyplot plus numpy in one namespace, by any of
      its spellings - `import pylab`, `from pylab import plot`,
      `from pylab import *`, `import matplotlib.pylab as pl`, or
      `from matplotlib import pylab`;
    * reaching it through the module the calculation context already provides -
      `matplotlib.pyplot.plot(...)` with no import at all, because
      DEFAULT_CALCULATION_CONTEXT hands procedures `matplotlib` whole, and
      equally `import matplotlib as mpl` then `mpl.pyplot.plot(...)`, so any
      alias the procedure gave matplotlib has to be followed.

    A syntax error is not this function's problem: it returns nothing and lets
    whatever reports broken procedures report it.
    """
    import ast

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []

    # pylab is pyplot re-exported, so it shares the same figure state.
    pyplot_modules = ('matplotlib.pyplot', 'matplotlib.pylab', 'pylab')

    # Two passes, so that `mpl.pyplot` is recognised wherever the
    # `import matplotlib as mpl` that named it happens to sit.
    found = set()
    matplotlib_aliases = {'matplotlib'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'matplotlib':
                    matplotlib_aliases.add(alias.asname or 'matplotlib')
                elif alias.name in pyplot_modules:
                    found.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == 'matplotlib':
                for alias in node.names:
                    if alias.name in ('pyplot', 'pylab'):
                        found.add(alias.asname or alias.name)
            elif node.module in pyplot_modules:
                # `from matplotlib.pyplot import plot`, or `from pylab import *`:
                # the names are pyplot's own, so report the module.
                found.add(node.module)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ('pyplot', 'pylab'):
            if isinstance(node.value, ast.Name) and node.value.id in matplotlib_aliases:
                found.add('matplotlib.' + node.attr)

    return sorted(found)


@register(Tags.database)
def check_calculation_procedures_use_pyplot(app_configs=None, databases=None, **kwargs):
    """Warn when a calculation procedure draws with pyplot.

    `matplotlib.pyplot` keeps its figures in module-level state, so two
    procedures plotting at once in one process share it. QATrack+ makes that
    worse rather than better: `cleanup_matplotlib` in `qa/views/perform.py` calls
    `plt.clf()` and `plt.close('all')` after a view that may have plotted, and
    both act on **every** figure in the process rather than this request's. The
    function's own docstring says pyplot is not threadsafe, and the
    `except KeyError` wrapped round it is commented as failing "when multiple
    uploads are being analyzed at same time" - which is this, already observed.

    **Every deployment is exposed, and no server configuration avoids it.**
    `CompositePerformer.calculate` works out every composite test in a test list
    inside a single request, and `cleanup_matplotlib` runs only after the last
    one (`perform.py:733`), so two procedures written the old way share a figure
    with no threads involved at all: the second one's saved plot carries the
    first one's line. A threaded server - the shipped Windows deployment's
    CherryPy pool, or Apache mod_wsgi, which defaults to 15 threads - adds a
    second way for figures to collide, between concurrent requests. gunicorn
    with sync workers avoids only that second case.

    That correction is nsmela's, on q#904: an earlier version of this check told
    Linux and Docker sites they were "not exposed", and for a check whose whole
    job is telling a clinic whether its QC plots can be wrong, that is the one
    answer it must not give wrongly.

    So this reports what it can establish - that the procedures are written the
    vulnerable way - and the hint says how the figures get mixed up. A Warning,
    never an Error: nothing is repaired by refusing to let them migrate.

    The failure is not a crash. It is a plot saved against the wrong test, or an
    empty one, in a record a physicist will read as evidence.

    Registered under Tags.database, so it runs on `migrate` and on
    `check --database <alias>` and costs nothing on every other command.
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

        # Unreachable or un-migrated is not this check's business: other
        # checks report a broken connection, and a fresh install's first
        # `migrate` must not be derailed by a diagnostic.
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
            "at the same time, or one after another in the same test list, can "
            "take each other's figures - and "
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
                "Every deployment can be affected. All the composite tests in "
                "a test list are calculated in one request, and pyplot is only "
                "cleared after the last one, so a procedure that draws on the "
                "current pyplot figure can pick up the plot of the procedure "
                "that ran before it. On a threaded server - the shipped Windows "
                "deployment's CherryPy thread pool, or Apache mod_wsgi (15 "
                "threads by default) - two requests can also take each other's "
                "figures. gunicorn with sync workers avoids only that second "
                "case. This is a warning, not an error: nothing here stops you "
                "migrating."
            ),
            id='qatrack.W012',
        )
    ]
