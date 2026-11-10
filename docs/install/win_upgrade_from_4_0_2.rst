.. _win_upgrade_from_4_0_2:

Upgrading a Windows Server 4.0.2 installation to 4.1
====================================================

On Windows Server the upgrade is a backup, a **branch change**, a dependency sync
and a service restart. There are no migrations to apply as this guide is written,
but you run ``migrate`` anyway, because that is what confirms the database and
the code agree.

Unlike the upgrades inside the 4.0 series, you name a version here exactly once:
the installation guide checked out ``releases/4.0``, and 4.1 lives on
``releases/4.1``.

.. note::

    Run these from an elevated PowerShell prompt, in the QATrack+ directory
    (``C:\deploy\qatrackplus`` in the installation guide).

.. include:: _upgrade_4_1_before.rst

Running the upgrade
-------------------

Stop the service and the scheduled task first, so nothing runs mid-upgrade. The
names are the ones the installation guide created:

.. code-block:: powershell

    Stop-Service QATrack+
    Stop-ScheduledTask -TaskName "QATrack+ Django Q Cluster"

Back up the database with SQL Server's own tooling and confirm the backup is
readable before going further - see :ref:`qatrack_backup`. A file copy of a live
database is not a backup.

Back up the uploaded files too. **They are not in the database**:

.. code-block:: powershell

    Compress-Archive -Path .\qatrack\media -DestinationPath $HOME\qatrackplus-media-pre-4.1.zip

Now change branches. This is the step that differs from every 4.0.x upgrade:

.. code-block:: powershell

    git fetch origin
    git checkout releases/4.1
    git pull

If ``git checkout`` refuses because you have local modifications, **stop and read**
*Upgrading an installation you have modified* below rather than forcing it.

Sync the dependencies. On Windows a site needs its extras - CherryPy, pywin32,
mssql-django and the LDAP packages - so use the same command the installation
guide gave you rather than a bare ``uv sync``, which is exact by default and
would uninstall them:

.. code-block:: powershell

    uv sync --frozen --extra win --extra mssql

.. warning::

    **A bare** ``uv sync`` **will break a Windows site.** It removes everything the
    lock file does not name for the default set, which on Windows includes the
    web server you are running under. If you are unsure which extras your site
    was installed with, check the command in :ref:`win_install_40` before running
    this one.

Apply migrations, collect the static files, and restart:

.. code-block:: powershell

    .venv\Scripts\python.exe manage.py migrate
    .venv\Scripts\python.exe manage.py collectstatic --noinput
    Start-Service QATrack+
    Start-ScheduledTask -TaskName "QATrack+ Django Q Cluster"

``migrate`` printing *"No migrations to apply."* is the expected result as this
guide is written - see *Migrations* above.

.. include:: _upgrade_4_1_after.rst
