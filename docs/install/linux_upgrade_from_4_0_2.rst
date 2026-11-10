.. _linux_upgrade_from_4_0_2:

Upgrading an Ubuntu Linux 4.0.2 installation to 4.1
===================================================

On Ubuntu Linux the upgrade is a backup, a **branch change**, a dependency sync
and a restart. There are no migrations to apply as this guide is written, but
you run ``migrate`` anyway, because that is what confirms the database and the
code agree.

Unlike the upgrades inside the 4.0 series, you name a version here exactly once:
the installation guide checked out ``releases/4.0``, and 4.1 lives on
``releases/4.1``. After this upgrade a ``git pull`` moves you between 4.1.x
releases, as before.

.. note::

    Every command below is run as the ``qatrack`` user. From a root shell,
    ``sudo -u qatrack -i`` gets you there; the account still needs to be able to
    ``sudo``, because stopping and starting the services does.

.. include:: _upgrade_4_1_before.rst

Running the upgrade
-------------------

Stop the services first, so nothing runs mid-upgrade:

.. code-block:: bash

    sudo supervisorctl stop gunicorn django-q2
    sudo service nginx stop

.. note::

    **Stop** ``django-q2`` **as well as** ``gunicorn``. The task runner is its own
    program, so stopping nginx does not stop it: it keeps its Python already
    imported while you replace the dependencies underneath it, and then fails in
    ways that look nothing like an upgrade problem.

Back up the database now, with the services stopped, and confirm the backup is
readable before you go any further - see :ref:`qatrack_backup`:

.. code-block:: bash

    pg_dump -U qatrack -Fc qatrackplus > ~/qatrackplus-pre-4.1.dump
    pg_restore --file=/dev/null ~/qatrackplus-pre-4.1.dump && echo "backup reads OK"

.. note::

    **Which account you run** ``pg_dump`` **from matters.** It connects over the
    local socket, where PostgreSQL identifies you by your operating-system name,
    so it works because you *are* ``qatrack``. From any other account it is
    refused; either switch user first, or add ``-h 127.0.0.1`` and give the
    password from ``local_settings.py``.

On MySQL, the equivalent. ``--single-transaction`` keeps the dump consistent, and
the last line a complete ``mysqldump`` writes is ``-- Dump completed``, so its
absence is how you tell a truncated file from a finished one:

.. code-block:: bash

    mysqldump -u qatrack -p --single-transaction --routines qatrackplus \
        > ~/qatrackplus-pre-4.1.sql
    tail -1 ~/qatrackplus-pre-4.1.sql | grep -q 'Dump completed' && echo "backup reads OK"

Back up the uploaded files too. **They are not in the database**, and a dump plus
a copy of ``local_settings.py`` is not a complete set without them:

.. code-block:: bash

    tar -czf ~/qatrackplus-media-pre-4.1.tar.gz -C ~/web/qatrackplus qatrack/media

Now change branches. This is the step that differs from every 4.0.x upgrade:

.. code-block:: bash

    cd ~/web/qatrackplus
    git fetch origin
    git checkout releases/4.1
    git pull

If ``git checkout`` refuses because you have local modifications, **stop and read**
*Upgrading an installation you have modified* below rather than forcing it. The
refusal is git protecting an edit you made.

Sync the dependencies. ``uv sync`` is exact by default: it installs what the lock
file names and uninstalls what it does not, which is what you want here:

.. code-block:: bash

    cd ~/web/qatrackplus
    uv sync --frozen

Apply migrations, collect the static files, and restart:

.. code-block:: bash

    .venv/bin/python manage.py migrate
    .venv/bin/python manage.py collectstatic --noinput
    sudo supervisorctl start gunicorn django-q2
    sudo service nginx start

``migrate`` printing *"No migrations to apply."* is the expected result as this
guide is written - see *Migrations* above.

.. include:: _upgrade_4_1_after.rst
