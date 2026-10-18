.. _docker_upgrade_from_4_0_1:

Upgrading an existing Docker 4.0.x installation
===============================================

This release reorganises the Docker deployment. There are **no database
migrations**, and your data is untouched, but two things will stop the upgrade
part-way if you are not expecting them: a file that used to be tracked in git,
and the fact that the container no longer runs as root.

Read this page before you start. Both steps below were measured on an upgrade
of a working 4.0.1 Docker installation, 2026-10-18.

What changed
------------

* The containers run as the unprivileged user ``uid 999`` instead of root.
* Media and static files are mounted at ``/app_data/media`` and
  ``/app_data/static`` rather than under ``/usr/src/qatrackplus``.
* ``deploy/docker/.env`` is no longer tracked in git. It holds your passwords,
  so it should never have been.
* ``compose.override.yaml`` — which docker compose loaded automatically, giving
  every installation the development bind mount — is now ``compose.dev.yaml``,
  loaded only when you ask for it.
* There is a new ``django-q`` service running the task cluster, and a
  ``user-data`` volume holding ``secret_key.txt``.
* The secret key is generated once and kept in the ``user-data`` volume unless
  you set ``SECRET_KEY`` in ``.env``. Everyone is signed out on the first
  restart after the upgrade; accounts and passwords are unaffected.

.. include:: _upgrade_4_0_before.rst

Before you start
----------------

Take a backup, and keep a copy of your ``.env`` somewhere outside the
repository — you are about to need it:

.. code-block:: bash

    cd ~/web/qatrackplus/deploy/docker
    cp .env ~/qatrackplus-env-backup
    docker compose exec backup /backup.sh

Step 1: let git replace the tracked ``.env``
--------------------------------------------

``git pull`` stops with::

    error: Your local changes to the following files would be overwritten by checkout:
        deploy/docker/.env
    Please commit your changes or stash them before you switch branches.
    Aborting

This is the tracked example ``.env`` the old deployment shipped, with your
edits in it. With the copy you made above, discard it and pull:

.. code-block:: bash

    cd ~/web/qatrackplus
    git checkout -- deploy/docker/.env
    git pull
    cp ~/qatrackplus-env-backup deploy/docker/.env

Your old settings keep working: ``POSTGRES_USER``, ``POSTGRES_PASSWORD``,
``POSTGRES_DB``, ``ALLOWED_HOSTS`` and ``CSRF_TRUSTED_ORIGINS`` mean the same
things they did. ``deploy/docker/.env.example`` documents what you can now add
to it, including ``SITE_NAME``, ``SITE_DOMAIN`` and ``SECRET_KEY``.

Step 2: give the new container user ownership of its volumes
-------------------------------------------------------------

The old image ran as root, so everything in your media and static volumes is
owned by root. The new one runs as ``uid 999`` and will not be able to write
there. If you skip this step the django container fails its system checks,
exits, is restarted by docker, and fails again — a crash loop whose logs read::

    ERRORS:
    ?: (qatrack.E001) The Django server process does not have write permissions to '/app_data/media'.

and ``docker compose up -d`` exits non-zero with ``dependency failed to start:
container qatrackplus-django-1 is unhealthy``.

So, with the stack stopped, hand both volumes to ``999``:

.. code-block:: bash

    cd ~/web/qatrackplus/deploy/docker
    docker compose down
    docker run --rm \
        -v qatrackplus_media-volume:/media \
        -v qatrackplus_static-volume:/static \
        alpine chown -R 999:999 /media /static

Use ``docker volume ls`` to confirm the volume names; they are prefixed with
the compose project name. If you use bind mounts (``MEDIA_DIR``), run
``sudo chown -R 999:999`` on those directories instead.

.. note::

    999 is the default. If you build the image with ``HOST_UID``/``HOST_GID``
    set to something else, use that instead — ``docker compose run --rm django
    id`` prints what the image actually uses.

Running the upgrade
-------------------

.. code-block:: bash

    cd ~/web/qatrackplus/deploy/docker
    docker compose build
    docker compose up -d
    docker compose exec django python manage.py check
    docker compose exec django python manage.py migrate

The first boot is slower than later ones — the entrypoint runs migrations and
collects static files before the web server binds — and ``docker compose up
-d`` waits for the health check to pass, so expect it to sit for a minute or
two before returning.

Checking the result
-------------------

``manage.py check`` should report no issues, and all five services should be
``healthy``:

.. code-block:: bash

    docker compose ps

Then sign in. You will be asked for your password again even if you had a
session open, because the secret key is new.

.. include:: _upgrade_4_0_after.rst
