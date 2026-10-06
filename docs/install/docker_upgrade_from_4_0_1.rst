.. _docker_upgrade_from_4_0_1:

Upgrading a Docker 4.0.1 installation to 4.0.2
===============================================

4.0.2 is a patch release that **does run database migrations**, unlike 4.0.1. On
Docker the upgrade is a backup, a code update, a rebuild and the migrations:

1. **Back up the database, and confirm the backup opens**
2. ``git fetch`` and ``git pull``
3. ``docker compose build``
4. ``docker compose up -d``
5. ``manage.py check --database default`` and ``manage.py migrate`` inside the container

You never name a version. The installation guide checks out the ``releases/4.0``
*branch* rather than a version tag, so the branch carries each patch as it is released
and a ``git pull`` is all that moves you between them.

**These steps apply to any 4.0.x patch**, not only this one. What changes between
patches is in the next section.

.. include:: _upgrade_4_0_1_before.rst

Running the upgrade
-------------------

Back up the database first and confirm the dump is readable. The deployment already
has a ``backup`` service that does this nightly with ``pg_dump``; run it once now, and
check the dump it wrote — :ref:`qatrack_backup` covers what a backup set must contain:

.. code-block:: bash

    cd ~/web/qatrackplus/deploy/docker
    docker compose exec backup bash /backup.sh
    ls -t backups/db_*.dump | head -1

Then verify that dump in the same container, which has ``pg_restore`` available.
Substitute the filename you just listed:

.. code-block:: bash

    docker compose exec backup pg_restore --list /backups/db_YYYYMMDD_HHMMSS.dump > /dev/null \
        && echo "backup reads OK"

Then fetch the new version and rebuild:

.. code-block:: bash

    cd ~/web/qatrackplus
    git fetch origin
    git pull
    cd deploy/docker
    docker compose build
    docker compose up -d

Check the installation and run the migrations inside the container. **This release has
migrations**, so ``migrate`` will report work done:

.. code-block:: bash

    docker compose exec django python manage.py check --database default
    docker compose exec django python manage.py migrate

.. note::

    ``manage.py check`` reports configuration problems, not data problems — it will not
    tell you whether your backup contains a database. Checking that is step one above,
    not something the command can do for you.

.. include:: _upgrade_4_0_1_after.rst
