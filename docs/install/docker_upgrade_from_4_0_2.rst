.. _docker_upgrade_from_4_0_2:

Upgrading a Docker 4.0.2 installation to 4.1
============================================

On Docker the upgrade is a backup, a **branch change**, an image rebuild and a
restart. There are no migrations to apply as this guide is written; the
container runs ``migrate`` itself on start, so there is nothing extra for you to
type.

Unlike the upgrades inside the 4.0 series, you name a version here exactly once:
the installation guide checked out ``releases/4.0``, and 4.1 lives on
``releases/4.1``.

.. include:: _upgrade_4_1_before.rst

Running the upgrade
-------------------

Back up first, with the stack running, using the documented commands in
:ref:`qatrack_backup`. Confirm the backup opens before going further.

Change branches. This is the step that differs from every 4.0.x upgrade:

.. code-block:: bash

    cd ~/web/qatrackplus
    git fetch origin
    git checkout releases/4.1
    git pull

.. note::

    If ``git checkout`` refuses, it has found a change you made. ``deploy/docker/.env``
    is ignored and so is not the cause. Read *Upgrading an installation you have
    modified* below rather than forcing it.

Rebuild the images and bring the stack back up:

.. code-block:: bash

    cd deploy/docker
    docker compose build
    docker compose up -d

The ``django`` container runs ``migrate`` and ``collectstatic`` on start, so
watch its log rather than running them yourself:

.. code-block:: bash

    docker compose logs -f django

.. warning::

    **A plain** ``docker compose build`` **reuses cached layers.** That is what you
    want for the application image, whose dependencies are pinned in
    ``uv.lock``. It is *not* enough for anything whose content comes from a
    package manager at build time - the ``backup`` container installs its tools
    with ``apk``, and that layer is cached. If you need its packages refreshed,
    rebuild it with ``docker compose build --no-cache backup``.

.. include:: _upgrade_4_1_after.rst
