.. This file is a fragment, pulled into each platform's 4.0.1 to 4.0.2 upgrade guide
   with `.. include::`. It is excluded from the build in conf.py, because an included
   file that is also read as a document has every label in it reported as a
   duplicate.

   It holds what is true of the release regardless of how QATrack+ is deployed, so
   the per-platform guides differ only where the commands differ.

Before you start
----------------

**Back up your database and your uploads first, and check the backup opens.** This
release runs migrations, which the previous patch release did not.

.. danger::

    **4.0.2 changes your database schema.** 4.0.1 did not, so if your upgrade
    routine has never had to account for migrations, this is the release where it
    does.

    Nothing here deletes data. The migrations record field descriptions the models
    have always declared, and restore unique constraints that SQL Server lost during
    the 4.0 upgrade. But a schema change is a schema change: take the backup, and
    confirm it is readable before you begin. :ref:`qatrack_backup` says what a backup
    set has to contain, and - if your production database is SQLite - how to take one
    that is actually readable, which a file copy of a live database is not.

.. dropdown:: If you are on SQL Server, read this one
    :color: warning
    :icon: alert

    The 4.0 migrations silently dropped unique indexes on SQL Server -
    ``mssql-django`` drops them when an unrelated field change retypes a primary
    key, and never puts them back. **Your database has been accepting duplicate
    rows that other backends would reject**, including on
    ``TestListInstance.user_key``, whose job is to keep API submissions unique.

    **4.0.2 restores them.** You do not have to do anything, but two things are
    worth knowing:

    - **``migrate`` prints a warning for each missing constraint**
      (``qatrack.W011``) before it applies anything, and then the same ``migrate``
      repairs them. The warnings are not telling you to act.

      To see them without migrating, the command is ``python manage.py check
      --database default``. **Plain ``manage.py check`` will not show them**: this
      check has to ask the database what it enforces, so it is registered to run only
      when a connection is in play, and ``check`` without ``--database`` reports
      "System check identified no issues" on a database that is missing all sixteen.
    - **Rows that already violate a constraint block its repair.** Run
      ``manage.py check_unique_constraints`` first to see whether you have any. A
      constraint that cannot be created is reported and skipped; the upgrade still
      finishes.

.. dropdown:: Dates and times will look different, and that is this release
    :color: warning
    :icon: alert

    **Dates now display as ``YYYY-MM-DD`` by default**, in every language, and the
    date pickers write back the same format they show.

    This is the fix for a released bug: 4.0 wrote a date into a form in one format
    and read it back in another, so a pre-filled date was silently replaced with an
    unrelated one - usually months away and at midnight - before anyone had touched
    the page.

    If your site needs its previous appearance, set ``QATRACK_DATE_FORMAT`` and
    ``QATRACK_DATETIME_FORMAT`` in ``local_settings.py``. The release notes give the
    values that reproduce 4.0's display.
