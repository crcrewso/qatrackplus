.. _linux_upgrade_from_4_0:

Upgrading an Ubuntu Linux 4.0.0 installation to 4.0.1
=======================================================

4.0.1 is a patch release containing **no database migrations**. On Ubuntu Linux the
upgrade is a code update, a dependency sync and a restart:

1. Stop the background services
2. ``git fetch`` and ``git pull``
3. ``uv sync`` with your database's extra
4. ``python manage.py check``
5. ``python manage.py migrate`` and ``python manage.py collectstatic``
6. Fix the ownership of the ``logs`` and ``qatrack/media`` folders (once)
7. Start the services again

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

Running the upgrade
-------------------

Stop the services first, so nothing runs mid-upgrade:

.. code-block:: bash

    sudo service nginx stop
    sudo supervisorctl stop gunicorn django-q2

.. warning::

    ``gunicorn`` matters as much as ``django-q2`` here, and earlier versions of
    this page did not mention it. Supervisor runs it as its own program, so
    stopping nginx does not stop it: it keeps its Python already imported while
    you replace the dependencies and the templates underneath it. What you get
    is old code serving new templates and new static files, which fails in ways
    that look nothing like an upgrade problem.

Fetch the new version. If you installed from the ``releases/4.0`` branch — which is
what the installation guide uses — this is a ``pull``, and you do not name a version at
all:

.. code-block:: bash

    cd ~/web/qatrackplus
    git fetch origin
    git pull

.. note::

    If ``git pull`` reports that you are not on a branch, you are on a tag from an
    earlier install. ``git checkout releases/4.0`` once, and every upgrade after that is
    the ``pull`` above.

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

.. dropdown:: For Active Directory / LDAP authentication
    :color: warning

    **If this site authenticates against Active Directory or another LDAP
    directory, add the ldap extra to the command above.**

    ``python-ldap`` is compiled from source on Linux, so install its build
    headers **first** - the sync fails partway through without them:

    .. code-block:: bash

        sudo apt install libldap2-dev libsasl2-dev

    Then run the sync with the extra added:

    .. code-block:: bash

        cd ~/web/qatrackplus
        uv sync --extra postgres --extra ldap

    .. note::

        The ``ldap`` extra arrived in **4.0.2**. You have it because this page
        upgrades the ``releases/4.0`` *branch*, which carries the whole 4.0
        series. If the installation was deliberately pinned to the ``v4.0.0``
        or ``v4.0.1`` tag, ``uv`` stops with *"Extra `ldap` is not defined"*;
        there the routes are the ``mssql`` extra, which has always carried
        ``python-ldap``, or
        ``uv pip install python-ldap 'django-auth-ldap<4.9'`` after the sync -
        and a package installed that way is removed by the next ``uv sync``.

    ``uv sync`` is exact: it installs what the command names and uninstalls
    everything else. Neither the ``postgres`` nor the ``mysql`` extra carries
    ``python-ldap``, and nothing about Active Directory requires SQL Server, so
    running the sync without ``--extra ldap`` **removes it**.

    **Without it, nobody can sign in at all** - not just directory users. The
    import error is swallowed where the backend imports it, so the backend
    loads and the site starts; but Django builds every backend in
    ``AUTHENTICATION_BACKENDS`` before any of them authenticates, and building
    the Active Directory one touches the missing module. Every sign-in attempt
    then raises from inside the login view and the page returns a server error,
    whatever order the backends are in and whoever is signing in - a local
    account does not get you in, because it never gets its turn.

    **QATrack+ does not warn you about this.** Nothing in the upgrade reports
    a missing ``python-ldap``, so confirm it yourself after the sync and
    before restarting:

    .. code-block:: bash

        python -c "import ldap; print(ldap.__version__)"

    If that prints a version you are fine. If it raises ``ModuleNotFoundError``
    the sync removed it, and directory sign-in will be broken when the site
    comes back up.

Check the installation before touching the database. This validates your settings
against the new code and is the cheapest way to catch a problem while the services are
still stopped:

.. code-block:: bash

    python manage.py check

Then run the migration step and collect the static files. **There are no migrations in
this release**, so ``migrate`` will report nothing to do — run it anyway, so that a
future release cannot find the database a step behind. ``collectstatic`` is not
optional: this release changes JavaScript and templates.

.. code-block:: bash

    python manage.py migrate
    python manage.py collectstatic

Next, fix the ownership of your ``logs`` and ``qatrack/media`` folders. The 4.0.0
installation guide gave these folders to ``www-data``, but Gunicorn and Django-Q2 run
as the local OS user for QATrack+ services. On an installation set up that way,
uploading an attachment to a Service Event or Test List can fail with a permission
error (`#836 <https://github.com/qatrackplus/qatrackplus/issues/836>`__). These
commands give the folders to your user, keep ``www-data`` as the group so Nginx can
still serve uploaded files, and make new folders inherit that group. You only need to
do this once, and it is safe to run again on an installation that is already correct:

.. code-block:: bash

    cd ~/web/qatrackplus
    sudo chown -R $USER:www-data logs qatrack/media
    sudo find logs qatrack/media -type d -exec chmod 2775 {} +
    sudo find logs qatrack/media -type f -exec chmod 664 {} +

Run these as the same user that runs QATrack+ (the one named in your Supervisor
configuration), not from a ``root`` shell: ``$USER`` would then be ``root``.

Restart - the application servers first, so nginx has something to proxy to
the moment it comes back:

.. code-block:: bash

    sudo supervisorctl start gunicorn django-q2
    sudo service nginx start

Confirm both are running before you call the upgrade done:

.. code-block:: bash

    sudo supervisorctl status

.. include:: _upgrade_4_0_after.rst
