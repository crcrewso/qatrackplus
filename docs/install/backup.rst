.. _qatrack_backup:

Backing up QATrack+
===================

It is **highly** recommended you put an automated backup solution in place for
your QATrack+ installation. We expect users to consult with their internal IT
departments for guidance on implementing a robust, automated backup strategy.

At a minimum, you must ensure that you keep secure, off-server backups of:

1. Your database (e.g., SQL Server, PostgreSQL, MySQL)
2. Your ``local_settings.py`` file (located in ``qatrackplus\qatrack\local_settings.py`` or ``qatrackplus/qatrack/local_settings.py``)
3. Your ``media`` folder (located in ``qatrackplus\qatrack\media`` or ``qatrackplus/qatrack/media``)

It is highly recommended that your backups do not reside on the QATrack+ server itself.
Store them on a remote system (e.g. a network or shared drive) so that if your server
loses its primary hard drive, or if the files become corrupted or locked by ransomware,
you will still have access to your backups.

.. danger::

    Ultimately, **it is up to you and your IT department to ensure your QATrack+
    installation is backed up correctly**.


The ``backup_site`` Management Command
--------------------------------------

``manage.py backup_site`` writes the database and the uploaded media files to a
timestamped directory.

.. warning::

    **It can only back up the database on SQL Server and SQLite.** On PostgreSQL,
    MySQL, or any other engine it reports that it cannot, and skips the database.

    **The command exits zero either way.** There is no non-zero exit path in it, so
    a scheduled task that checks only the exit status will record a success. Check
    the output, or check that a database file is in the backup directory.

    **On MySQL, check any backup set produced before 4.0.1.** Earlier versions
    skipped the database silently on MySQL and still reported success, so a backup
    set can contain media and settings and no database at all. Use ``mysqldump``.

    **On PostgreSQL this command has never written a database backup.** It has
    always said so rather than failing quietly, but if you have been relying on it,
    you do not have one. Use ``pg_dump``, or the Docker script below, which does
    exactly that.

Backups in Docker
-----------------

``deploy/docker/backup/backup.sh`` reads the database connection from the
environment rather than hard-coding it:

.. code-block:: bash

    POSTGRES_DB        # the database to dump
    POSTGRES_USER      # the role to connect as
    POSTGRES_PASSWORD  # that role's password

These are the same variables the ``postgres`` service uses, so a deployment that
sets them in its Compose environment or ``.env`` file needs no further
configuration. If they are not set the dump fails rather than silently writing a
backup of the wrong database.

.. note::

    Before 4.0.1 this script had the database name and user written into it, so a
    deployment that had changed either was dumping the wrong database, or nothing at
    all. If you have customised them, confirm your next backup contains what you
    expect.


Using Django to Dump The Database To JSON
-----------------------------------------

.. warning::
    **Do NOT use this method for your regular database backups.**
    Dumping to JSON is slow, memory-intensive, and is not a reliable backup strategy for a production database. Always use the native backup tools provided by your database engine (e.g. ``pg_dump`` for PostgreSQL, or SQL Server Management Studio for MS SQL) for your regular backups.

It is, however, the only backup format that does not care which database engine you
are running, so it is the right tool for two jobs: **moving a site between engines**
(SQL Server to PostgreSQL, say) and **seeding a test or demonstration instance** from
a known state.

**What has actually been tested, and what has not.** The commands below were tested
end to end in exactly one configuration:

.. list-table::
    :header-rows: 1
    :widths: 40 60

    * - Tested
      - Not tested
    * - QATrack+ 4.0.1 → 4.0.1
      - any version change, e.g. 4.0.1 → 4.0.2
    * - PostgreSQL 16.15 → PostgreSQL 16.15
      - **any change of engine**, in either direction
    * - Ubuntu 24.04 → the same server
      - a different server, or Linux ↔ Windows
    * - 3,460 objects
      - a site of clinical size

A site of 3,460 objects was dumped, its database dropped, and the site rebuilt from
the dump alone; every object count matched the original.

.. warning::

    **Engine migration is the use this format exists for, and it is the case that has
    not been tested.** Nothing below has been exercised across SQL Server, MySQL or
    SQLite, nor between two different engines. Treat a cross-engine move as something
    to rehearse on a copy first, verify by restoring, and compare object counts
    against the source - not as a procedure known to work.

    The same applies to a version change. ``loaddata`` writes rows directly, so a dump
    taken on one QATrack+ version carries that version's schema expectations; restore
    it onto the same version unless you have tested otherwise.

**Exporting**

.. code-block:: bash

    python manage.py dumpdata --indent 1 \
        -e contenttypes -e auth.permission -e sessions -e admin.logentry -e django_q \
        > qatrack-export.json

The exclusions matter. ``contenttypes`` and ``auth.permission`` are rebuilt by
``migrate`` and clash on import if they are in the file; ``sessions``,
``admin.logentry`` and ``django_q`` are transient and only make the file larger.

.. danger::

    **On 4.0.x, do not add ``--natural-foreign`` or ``--natural-primary``.** They produce
    a file that QATrack+ **cannot load back**. Three models - test list sublists, service
    areas and service types - define a natural key without the matching lookup the
    deserializer then needs, so a foreign key is written as a list and the import stops
    with::

        DeserializationError: Problem installing fixture ...
        ["“['Accelerator']” value must be an integer."]: (service_log.unitservicearea:pk=1)

    This was measured, not inferred - the restore failed at that line and left an empty
    database. Note where that leaves you: ``loaddata`` empties the tables it is loading
    into before it reaches the row it cannot resolve, so the attempt does not fail
    harmlessly. The plain integer-primary-key form above restores correctly.

    **This restriction is specific to the 4.0.x series.** The three missing lookups are
    fixed from 4.1 onwards, where the same export restores correctly. An export taken on
    4.1 with natural keys will still not load into a 4.0.x installation, which does not
    have those lookups.

**Restoring**

.. code-block:: bash

    # 1. an empty database, owned by your QATrack+ database user
    # 2. then:
    python manage.py migrate
    python manage.py createcachetable
    python manage.py loaddata qatrack-export.json

``createcachetable`` must come **before** ``loaddata``, for the same reason it does
during a fresh install: loading records fires cache-invalidation signals, and they
need the cache table to exist.

Do **not** run ``loaddata fixtures/defaults/*/*`` first. The export already contains
those rows, and loading them twice gives you duplicate categories, statuses and unit
types.

.. note::

    Verify a dump by restoring it, not by looking at it. A JSON file that was written
    without error can still be one your site cannot read back - which on 4.0.x is exactly
    what ``--natural-foreign`` produces.

Restoring from Backups
----------------------

If you need to restore your QATrack+ instance from a backup (for example, when migrating to a new server or recovering from an issue), follow the general guidelines below for your deployment platform.

Linux
.....

1. **Re-install QATrack+:** Follow the standard Linux installation instructions to rebuild your server. Ensure you check out the *exact same version* of QATrack+ that you were running when the backup was taken.
2. **Restore Database:** Consult your IT department to restore the database from your automated backups using the native database tools (e.g., ``pg_restore`` or ``mysql``).
3. **Restore Settings and Media:** Copy your backed-up ``local_settings.py`` file to the ``qatrackplus/qatrack/`` directory. Extract your backed-up ``media`` folder into the ``qatrackplus/qatrack/media/`` directory.
4. **Permissions and Restart:** Ensure the web server user (e.g., ``www-data``) has the correct ownership and permissions for the restored ``media`` folder. Finally, restart the web server and your background task runner.

Windows
.......

1. **Re-install QATrack+:** Follow the standard Windows installation instructions. Ensure you check out the *exact same version* of QATrack+ that you were running when the backup was taken.
2. **Restore Database:** Consult your IT department to restore your database using SQL Server Management Studio or native MS SQL backup tools.
3. **Restore Settings and Media:** Copy your backed-up ``local_settings.py`` file to the ``qatrackplus\qatrack\`` directory. Copy your backed-up ``media`` folder into the ``qatrackplus\qatrack\media\`` directory.
4. **Permissions and Restart:** Ensure the Windows Service account or IIS application pool has write permissions to the restored ``media`` folder. Finally, restart your QATrack+ Web Service and your Django Q Scheduled Task.

Docker
......

1. **Re-deploy Containers:** On a fresh Docker host, clone the QATrack+ repository and ensure you are on the *exact same version* (branch/tag) as your backup.
2. **Restore Database:** If you are using an external database, consult your IT department to restore it. If you are using a containerized database volume, follow Docker best practices to restore the database volume from your backup archives.
3. **Restore Settings and Media:** Restore your ``local_settings.py`` file and ``media`` files to the appropriate mounted volumes or host directories as configured in your ``docker-compose.yml``.
4. **Start Containers:** Run ``docker compose up -d`` to bring the restored QATrack+ containers back online.


Appendix: if your production database is SQLite
-----------------------------------------------

SQLite is documented here as a development and small-installation option, and some
sites run it in production anyway. This appendix is for them. **It describes one
hazard that will not announce itself**, and it is a documentation note rather than a
change to the command.

.. danger::

    **``manage.py backup_site`` copies the SQLite file while QATrack+ may be writing
    to it, and the copy is usually unusable.** It calls ``shutil.copy2`` on the live
    database. It does not use SQLite's online backup, and the copy carries no
    journal, so a copy taken while a transaction is open is a torn file.

    **Measured, five runs out of five:** with one thread writing continuously, every
    ``shutil.copy2`` copy failed ``PRAGMA integrity_check``, and one could not be
    opened at all - *"database disk image is malformed"*. Over the same runs,
    ``VACUUM INTO`` produced a consistent copy every time.

    The command prints ``Copied SQLite database to ...`` and **exits zero** in both
    cases, so nothing tells you which you have. A site can hold a year of backups
    that are all unopenable and have been told nothing was wrong.

**Back up SQLite with ``VACUUM INTO``**

``VACUUM INTO`` is SQLite's own online backup. It takes a read lock, so it is safe
while the site is in use, and it writes a compacted, consistent database:

.. code-block:: shell

    DB=/path/to/your/qatrack.db
    OUT=/path/to/backups/qatrack-$(date +%Y-%m-%d).db
    sqlite3 "$DB" "VACUUM INTO '$OUT'"

If ``sqlite3`` is not installed, Python's bundled module does the same thing:

.. code-block:: shell

    python -c "import sqlite3,sys; con=sqlite3.connect(sys.argv[1]); \
    con.execute('vacuum into ?', (sys.argv[2],)); con.close()" "$DB" "$OUT"

**Always verify the copy.** This is the step that distinguishes a backup from a file:

.. code-block:: shell

    sqlite3 "$OUT" "PRAGMA integrity_check;"      # must print: ok
    sqlite3 "$OUT" "SELECT COUNT(*) FROM qa_testinstance;"

A backup that prints anything other than ``ok`` is not a backup. Check it when you
make it, not when you need it.

**What to do with the shipped command**

``backup_site`` still backs up the uploaded media files usefully, so it is not
useless on SQLite - **treat its database step as not having happened.** Run
``VACUUM INTO`` alongside it, keep both outputs together, and verify the database
copy.

**Two further things worth knowing before you rely on SQLite in production**

- **One writer at a time.** SQLite serialises writes across the whole database, so a
  long write blocks every other write. QATrack+ runs a scheduled task process as well
  as the web process, so those two compete.
- **Upgrades work, and have been tested.** A populated v3.1.1.4 SQLite database
  migrates to 4.0 cleanly - 39 migrations, no errors, no rows lost - so this
  appendix is about your backups and not about your ability to upgrade.

  One caveat that affects nobody upgrading in place, but will catch anyone
  *installing* an old QATrack+ today to rehearse an upgrade: **Django 2.2, which
  v3.1.1.4 pins, cannot replay those migrations against a SQLite newer than 3.26.**
  The rebuild leaves foreign keys pointing at a dropped ``..._old`` table, and the
  error reads like data corruption. Rehearse on PostgreSQL, or on a SQLite of the
  period.
