.. _win_upgrade_from_4_0_1:

Upgrading a Windows Server 4.0.1 installation to 4.0.2
=======================================================

4.0.2 is a patch release that **does run database migrations**, unlike 4.0.1. On
Windows Server the upgrade is a backup, a code update, a dependency sync, the
migrations and a restart:

1. Stop the scheduled task and the web service
2. **Back up the database, and confirm the backup restores**
3. ``git fetch`` and ``git pull``
4. ``uv sync --exact --extra win --extra mssql``
5. ``python manage.py check``
6. ``python manage.py migrate`` and ``python manage.py collectstatic``
7. Start the service and scheduled task again

You never name a version. The installation guide checks out the ``releases/4.0``
*branch* rather than a version tag, so the branch carries each patch as it is released
and a ``git pull`` is all that moves you between them.

**These steps apply to any 4.0.x patch**, not only this one. What changes between
patches is in the next section.

.. important::

    Of the three deployments, Windows is the one where this release changes the
    database most: it is the SQL Server deployment, and the unique constraints the 4.0
    upgrade dropped are restored here. Read the SQL Server note below before you start.

.. include:: _upgrade_4_0_1_before.rst

Running the upgrade
-------------------

Stop the scheduled task and the web service:

.. code-block:: console

    >>  Stop-ScheduledTask -TaskName "QATrack+ Django Q Cluster"
    >>  Stop-Service "QATrack+ Web Service"

Back up the database with the service stopped, and verify the backup before going
further — see :ref:`qatrack_backup`. In SQL Server Management Studio, take a full
backup and then run a ``RESTORE VERIFYONLY`` against the file it produced:

.. code-block:: sql

    BACKUP DATABASE qatrackplus TO DISK = 'D:\backups\qatrackplus-pre-4.0.2.bak' WITH INIT;
    RESTORE VERIFYONLY FROM DISK = 'D:\backups\qatrackplus-pre-4.0.2.bak';

Fetch the new version and update the environment. You do not name a version — the
``releases/4.0`` branch you installed from carries the patch:

.. code-block:: console

    >>  cd C:\deploy\qatrackplus
    >>  git fetch origin
    >>  git pull
    >>  uv sync --exact --extra win --extra mssql

Check the installation. On SQL Server this is where the missing-constraint warnings
appear, and the ``migrate`` that follows is what repairs them — the warnings are not
asking you to act:

.. code-block:: console

    >>  python manage.py check
    >>  python manage.py check_unique_constraints

Then run the migrations and collect the static files:

.. code-block:: console

    >>  python manage.py migrate
    >>  python manage.py collectstatic

Restart:

.. code-block:: console

    >>  Start-Service "QATrack+ Web Service"
    >>  Start-ScheduledTask -TaskName "QATrack+ Django Q Cluster"

.. include:: _upgrade_4_0_1_after.rst
