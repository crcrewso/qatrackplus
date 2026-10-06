.. _linux_upgrade_from_4_0_1:

Upgrading an Ubuntu Linux 4.0.1 installation to 4.0.2
=====================================================

4.0.2 is a patch release that **does run database migrations**, unlike 4.0.1. On
Ubuntu Linux the upgrade is a backup, a code update, a dependency sync, the
migrations and a restart:

1. Stop the background services
2. **Back up the database, and confirm the backup opens**
3. ``git fetch`` and ``git pull``
4. ``uv sync`` with your database's extra
5. ``python manage.py check --database default``
6. ``python manage.py migrate`` and ``python manage.py collectstatic``
7. Start the services again

You never name a version. The installation guide checks out the ``releases/4.0``
*branch* rather than a version tag, so the branch carries each patch as it is released
and a ``git pull`` is all that moves you between them.

**These steps apply to any 4.0.x patch**, not only this one. What changes between
patches is in the next section.

.. include:: _upgrade_4_0_1_before.rst

Running the upgrade
-------------------

Stop the background services first, so no task runs mid-upgrade:

.. code-block:: bash

    sudo supervisorctl stop django-q2
    sudo service nginx stop

Back up the database now, with the services stopped, and confirm the backup is
readable before you go any further — see :ref:`qatrack_backup`:

.. code-block:: bash

    pg_dump -U qatrack -Fc qatrackplus > ~/qatrackplus-pre-4.0.2.dump
    pg_restore --list ~/qatrackplus-pre-4.0.2.dump > /dev/null && echo "backup reads OK"

Fetch the new version:

.. code-block:: bash

    cd ~/web/qatrackplus
    git fetch origin
    git pull

Update the Python environment. Use the extra that matches your database:

.. code-block:: bash

    cd ~/web/qatrackplus
    source .venv/bin/activate
    uv sync --extra postgres

.. dropdown:: For MySQL
    :color: warning

    .. code-block:: bash

        cd ~/web/qatrackplus
        uv sync --extra mysql

Check the installation before touching the database. ``--database default`` runs the
checks that need a connection as well as the ones that do not; on PostgreSQL and MySQL
they find nothing, because the constraint loss this release repairs only happened on
SQL Server:

.. code-block:: bash

    python manage.py check --database default

Then run the migrations and collect the static files. **This release has migrations**,
so ``migrate`` will report work done. ``collectstatic`` is not optional: this release
changes JavaScript and templates.

.. code-block:: bash

    python manage.py migrate
    python manage.py collectstatic

Restart:

.. code-block:: bash

    sudo service nginx start
    sudo supervisorctl start django-q2

.. include:: _upgrade_4_0_1_after.rst
