.. _docker_upgrade_from_4_0:

Upgrading a Docker 4.0.x installation
=====================================

The 4.0.x patch releases contain **no database migrations**. On Docker the upgrade is
a code update, a dependency sync and a restart:

1. ``git fetch`` and ``git pull``
2. ``docker compose build``
3. ``docker compose up -d``
4. ``manage.py check`` and ``manage.py migrate`` inside the container

You never name a version. The installation guide clones the repository without
choosing a branch, so your clone follows the default branch and a ``git pull`` is all
that moves you between patches. The ``migrate`` step above is still worth running: it
reports that there is nothing to do, which is a different thing from your not having
checked.

**These steps apply to any 4.0.x patch.** What changes between patches is in the next
section.

.. note::

    **If your clone was made on Windows before QATrack+ 4.0.2**, check it out again
    before building, or the scripts inside ``deploy/docker`` may still have Windows
    line endings and will fail inside the containers. See
    :ref:`checking out deploy/docker again <docker_line_endings>`, which keeps your
    own edits to ``.env``, ``nginx.conf`` and the compose files.

.. note::

    The service and scheduled task names stopped carrying version numbers in 4.0.0
    precisely so that patch upgrades would not require renaming anything. If you
    upgraded to 4.0.0 from v3.x, your service is called *QATrack+ Web Service* and your
    scheduled task *QATrack+ Django Q Cluster*.

.. include:: _upgrade_4_0_before.rst

.. _docker_upgrade_env_untracked:

Upgrading from 4.0.0 or 4.0.1: keep your ``.env``
-------------------------------------------------

From 4.0.2, ``deploy/docker/.env`` is no longer part of the QATrack+ repository,
because it holds your database password. Your copy has your own settings in it, so
on this one upgrade ``git pull`` stops with *Your local changes to the following
files would be overwritten*. Before the first pull to 4.0.2 or later, set your
``.env`` aside and put it back afterwards:

.. code-block:: bash

    cd ~/web/qatrackplus
    cp deploy/docker/.env ../qatrack.env.backup
    git checkout -- deploy/docker/.env
    git pull
    cp ../qatrack.env.backup deploy/docker/.env

Your ``.env`` is now ignored by git, and later pulls leave it alone. Compare it
with ``deploy/docker/.env.example``, which lists every setting you can now make
there: in particular set ``ALLOWED_HOSTS`` to the names people use to reach
QATrack+. Keep ``qatrack.env.backup`` somewhere safe, or delete it: it holds your
database password.

Running the upgrade
-------------------

From your ``deploy/docker`` directory:

.. code-block:: bash

    cd ~/web/qatrackplus
    git fetch origin
    git pull
    cd deploy/docker
    docker compose build
    docker compose up -d

Then check the installation and run the migration step inside the container:

.. code-block:: bash

    docker compose exec django python manage.py check
    docker compose exec django python manage.py migrate

Before restarting, re-read *What needs your attention in this release* above: the
backup script's environment variables changed in this release.

.. note::

    ``manage.py check`` reports configuration problems, not data problems — it will not
    tell you whether your backups contain a database or whether your groups have the
    permissions they need. Both are covered below.

.. include:: _upgrade_4_0_after.rst
