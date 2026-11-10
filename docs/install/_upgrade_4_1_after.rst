.. This file is a fragment, pulled into each platform's 4.0.2 to 4.1 upgrade guide
   with `.. include::`. See the header of _upgrade_4_1_before.rst.

After upgrading
---------------

**Check the site serves a page and a user can sign in** before you tell anyone
the upgrade is done. That is the whole of the smoke test for a release with no
migrations: if the code loaded and the database answers, there is no third thing
this upgrade could have broken.

**Confirm which version you are on.** The footer of any page reports it, and it
is worth looking at rather than assuming, because a checkout that failed part
way leaves a site that still runs - on the old code:

.. code-block:: text

    QATrack+ v4.1.0

.. admonition:: Check before release
    :class: warning

    If 4.1 ships anything that changes what an administrator sees - a permission
    label, a date format, a default - add the check for it here, the way the
    4.0.2 guide tells the reader to re-check their groups after the service
    event permission was renamed. As of 2026-11-10 there is no such item.

Running the test suite against an installed server
--------------------------------------------------

You do not need to, and most sites never will. It is worth knowing how, because
a suite that passes on your own server is the strongest evidence an upgrade
landed correctly on *your* data and *your* settings.

**The GUI tests are skipped for you, and the summary will say so.** Around forty
of them drive a real browser, which a server has no reason to have installed, so
plain ``pytest`` skips them and reports them as skips. That is not a gap in the
run and not a failure of your installation - it is the only thing that can be
done without a browser. Nothing needs passing on the command line:

.. code-block:: bash

    .venv/bin/python -m pytest

On Windows that is ``.venv\Scripts\python.exe -m pytest``.

If you do want them, install Chrome or Firefox on the server and add
``--run-selenium``. They drive a real browser against a real server, so the run
takes considerably longer, and they are not what tells you an upgrade landed.

.. note::

    If you are following a 4.0.x upgrade guide instead, it tells you to deselect
    the GUI tests with a marker expression. That is correct there: 4.0.x has no
    ``conftest.py``, so it neither skips them for you nor understands
    ``--run-selenium``. That form still works on 4.1, and is removed in 4.2.

.. warning::

    **Your own settings are in force while the suite runs**, because ``pytest``
    reads ``local_settings.py`` like everything else. Read
    :ref:`the developer guide's note on test settings <local_test_settings_templates>`
    before running it against a production machine.

Upgrading an installation you have modified
-------------------------------------------

If you have edited files inside ``qatrack/``, the branch change is where you
find out. Record what you changed **before** you switch:

.. code-block:: bash

    cd ~/web/qatrackplus
    git diff > ~/qatrack-local-changes-pre-4.1.patch
    git status --porcelain

Keep that patch somewhere outside the checkout. After the upgrade, re-apply what
still applies:

.. code-block:: bash

    git apply --3way ~/qatrack-local-changes-pre-4.1.patch

``--3way`` is what lets git tell you about a change that no longer fits, rather
than failing the whole patch. A hunk that conflicts is one you have to decide
about: the file underneath it moved in 4.1, and your edit may or may not still
be wanted.

.. note::

    A change you keep re-applying at every upgrade is usually a setting that
    wants to be in ``local_settings.py``, or a missing feature worth raising at
    the :mailinglist:`mailing list <>`. Carrying a patch across releases is
    the most expensive way to keep a change.
