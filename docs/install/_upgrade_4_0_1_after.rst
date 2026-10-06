.. A fragment. See the note at the top of _upgrade_4_0_1_before.rst.

After upgrading
---------------

**Check a date on a form.** Open a fault, a QC session or a service event that has
a pre-filled date and confirm it shows the date you expect. That is the fix this
release exists for, and it is visible in ten seconds.

**On SQL Server, confirm the constraints came back:**

.. code-block:: shell

    python manage.py check --database default

should now report nothing. **The ``--database`` is not optional here** - plain
``manage.py check`` cannot see these warnings at all, and will say there are no issues
whether or not every constraint is missing.

If it still reports ``qatrack.W011`` for a table, that constraint was skipped because
of duplicate rows. ``manage.py check_unique_constraints`` names them, and once they are
resolved the repair can be run again by reversing the migration for that app and
applying it forward:

.. code-block:: shell

    python manage.py migrate parts 0018_v4_0_final
    python manage.py migrate

Reversing removes the constraints that app's migration added and applying it forward
puts back every one it can - including the one that was skipped. A plain ``migrate``
on its own will not do it, because the migration is already recorded as applied.

.. dropdown:: If a calculation procedure is reported as using ``matplotlib.pyplot``

    ``manage.py check --database default`` may now report ``qatrack.W012`` against one
    or more of your calculation procedures - again, plain ``manage.py check`` will not
    show it. ``pyplot`` keeps its figures in state shared by
    everything in the same process, so two procedures plotting at once can take each
    other's figures, and the result is a plot saved against the wrong test.

    Whether it can happen depends on how you serve QATrack+ - the Windows deployment
    shares one process across requests and is exposed; the Linux and Docker
    deployments run one request per process and are not. The warning names each
    procedure and shows the ``UTILS.get_figure()`` form to replace it with. Nothing
    stops you upgrading.

**Confirm your backups once more** - if you act on one thing after this release,
make it reading the output of your next backup run rather than its exit status.
