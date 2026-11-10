.. This file is a fragment, pulled into each platform's 4.0.2 to 4.1 upgrade guide
   with `.. include::`. It is excluded from the build in conf.py, because an included
   file that is also read as a document has every label in it reported as a
   duplicate.

   It holds what is true of the release regardless of how QATrack+ is deployed, so
   the per-platform guides differ only where the commands differ.

   RELEASE TIME: three things in this file have to be re-checked before 4.1 ships -
   each is marked `.. admonition:: Check before release`. Measured 2026-11-10 against
   `upstream/develop`; if the answers have changed, this fragment is wrong rather
   than merely out of date.

Before you start
----------------

**Back up your database and your uploads, and check the backup opens.** That is
the same thing you would do before any QATrack+ upgrade.

**If you have edited any files inside** ``qatrack/``, read *Upgrading an
installation you have modified* at the end of this page **before you switch
branches**: it asks you to record what you changed while that is still a
one-line command.

This upgrade changes branches, which the 4.0.x ones did not
--------------------------------------------------------------

Every upgrade inside the 4.0 series was a ``git pull``: the installation guide
checked out ``releases/4.0`` once, and 4.0.0, 4.0.1 and 4.0.2 are all points on
that branch.

**4.1 is a different branch.** Moving to it is a ``git checkout``, and it is the
step most likely to stop with an error, because it is the step that notices
anything you have changed in the working tree. The platform page gives the exact
commands; two things are worth knowing before you run them:

- **A modified tracked file stops the checkout.** Git refuses rather than
  overwriting your change. That is the good case: you find out before anything
  moves. *Upgrading an installation you have modified* says how to record and
  re-apply such changes.
- **An ignored file is not protected.** ``qatrack/local_settings.py`` is ignored
  and therefore safe from git, but anything you have left in the tree that the
  new branch tracks will be overwritten without a word. If you are unsure, take
  a copy of the whole directory before you start - it is cheaper than finding
  out later.

.. note::

    Once you are on ``releases/4.1``, later 4.1.x upgrades are a ``git pull``
    again, exactly as they were within 4.0.

Migrations
----------

**As this fragment is written, 4.1 adds no migrations.** ``releases/4.0`` and
the 4.1 line carry an identical 227, so ``migrate`` has nothing to apply and
prints *"No migrations to apply."*

That is the same situation as the 4.0.1 upgrade, and it is normal rather than a
sign that something was skipped. **Run** ``migrate`` **anyway.** It costs
nothing, and it is what tells you the database and the code agree.

.. admonition:: Check before release
    :class: warning

    Re-measure this before 4.1 ships. If any migration has landed since, this
    section has to list it the way the 4.0.2 guide lists its eight, and say what
    it does to existing data:

    .. code-block:: bash

        git ls-tree -r --name-only releases/4.0 | grep '/migrations/.*\.py$' | sort > /tmp/a
        git ls-tree -r --name-only releases/4.1 | grep '/migrations/.*\.py$' | sort > /tmp/b
        comm -13 /tmp/a /tmp/b

    An empty result means this section is still correct.

What changes that you will notice
---------------------------------

.. admonition:: Check before release
    :class: warning

    This section is incomplete by construction: it can only be finished once 4.1
    is closed. Everything listed below was true of ``develop`` on 2026-11-10.
    Before release, walk the 4.1 entry in :doc:`../release_notes` and make sure
    every item an operator has to *act on* appears here - a release note the
    reader has to cross-reference is a step they will miss.

**The test suite no longer needs a marker to skip the GUI tests.** On 4.0.x a
plain ``pytest`` ran the browser tests and they errored at setup on a server
with no browser, so the upgrade guides told you to pass ``-m "not selenium"``.
From 4.1 they are skipped for you and reported as skips. The *After upgrading*
section below gives the new command.

The marker expression still works in 4.1 - it warns, and is removed in 4.2 - so
a command you have in a script or a runbook does not break on the day you
upgrade.
