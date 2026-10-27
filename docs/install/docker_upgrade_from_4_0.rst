.. _docker_upgrade_from_4_0:

Upgrading a Docker 4.0.0 installation to 4.0.1
================================================

4.0.1 is a patch release containing **no database migrations**. On Docker the
upgrade is a code update, a dependency sync and a restart:

1. ``git fetch`` and ``git pull``
2. ``docker compose build``
3. ``docker compose up -d``
4. ``manage.py check`` and ``manage.py migrate`` inside the container

You never name a version. The installation guide checks out the ``releases/4.0``
*branch* rather than a version tag, so the branch carries each patch as it is released
and a ``git pull`` is all that moves you between them.

**These steps apply to any 4.0.x patch**, not only this one. What changes between
patches is in the next section.

.. note::

    The service and scheduled task names stopped carrying version numbers in 4.0.0
    precisely so that patch upgrades would not require renaming anything. If you
    upgraded to 4.0.0 from v3.x, your service is called *QATrack+ Web Service* and your
    scheduled task *QATrack+ Django Q Cluster*.

.. include:: _upgrade_4_0_before.rst

.. _docker_upgrade_env_untracked:

.. include:: _docker_env_untracked.rst
.. _docker_upgrade_keep_secret_key:

Keep your users signed in (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From 4.0.2, QATrack+ keeps its secret key in a Docker volume, or takes it from
``SECRET_KEY`` in ``.env``. 4.0.0 and 4.0.1 kept it in your QATrack+ folder, at
``deploy/docker/user-data/secret_key.txt``. If you start 4.0.2 without carrying it
over, QATrack+ makes a new key: every user is signed out once, and password-reset
links sent before the upgrade stop working.

To keep the key, copy it into ``.env`` before you start 4.0.2 for the first time:

.. code-block:: bash

    cd ~/web/qatrackplus
    echo "SECRET_KEY=$(cat deploy/docker/user-data/secret_key.txt)" >> deploy/docker/.env

If that file does not exist, there is no key to carry over; skip this step. The
key signs your users' sessions: keep ``.env`` as private as your database
password.

.. _docker_upgrade_stale_follow_ups:

Clear follow-up emails that were never sent (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Docker installations before 4.0.2 did not run QATrack+'s background tasks, so
the follow-up emails of *QC Completed* notices set to *Follow up* were queued but
never sent. 4.0.2 runs background tasks, and the first time it starts it sends
every follow-up still waiting, all at once, however old. Only sites that set up
follow-up notices are affected.

While your current QATrack+ is still running, and before ``docker compose up -d``
starts 4.0.2, see how many are waiting:

.. code-block:: bash

    cd ~/web/qatrackplus/deploy/docker
    docker compose exec -T django python manage.py shell -c "from django.utils import timezone; from django_q.models import Schedule; print(Schedule.objects.filter(name__startswith='follow-up-for-tli-', schedule_type=Schedule.ONCE, next_run__lt=timezone.now()).exclude(repeats=0).count(), 'overdue follow-up emails')"

To remove them instead of sending them:

.. code-block:: bash

    docker compose exec -T django python manage.py shell -c "from django.utils import timezone; from django_q.models import Schedule; print(Schedule.objects.filter(name__startswith='follow-up-for-tli-', schedule_type=Schedule.ONCE, next_run__lt=timezone.now()).exclude(repeats=0).delete()[0], 'overdue follow-up emails removed')"

Follow-ups that are not due yet are kept, and are sent on time.

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
