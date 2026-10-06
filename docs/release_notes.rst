Release Notes
=============

.. This file holds the notes for the series currently being released, and nothing else.
   Each earlier major series lives in its own file under release_notes/ and is listed in
   the toctree at the bottom - not pulled in with `include`, so each is its own page.

   When starting a new series: move this file's sections into
   release_notes/<series>.rst, give that file a document title at `=` level and a
   `.. _release_notes_series_<n>:` label, add it to the toctree below, and begin the new
   series here.

.. _`release_notes_40`:

QATrack+ 4.0
~~~~~~~~~~~~~

4.0.2
-----

**This release runs database migrations; 4.0.1 did not.** Nothing in them deletes
data, but take a backup and confirm it opens before you upgrade - see
:ref:`linux_upgrade_from_4_0_1`, :ref:`win_upgrade_from_4_0_1` or
:ref:`docker_upgrade_from_4_0_1`.

Bug Fixes
^^^^^^^^^

Ordered by consequence, most serious first.

* **Forms no longer record the wrong date and time.** Where a date field arrives
  already filled in - the fault form's *Date & Time fault occurred*, a QC session's
  *Work Completed*, a service event's date - the server wrote that value in one
  format and the date picker read it back in another. The picker then replaced it
  with an unrelated date, usually months away and at midnight, before anyone had
  touched the page.

  Nothing indicated it had happened: the replacement was a well-formed date in the
  expected format, sitting in a field the user had not edited. A record saved
  without changing that field carried a time that was simply wrong. Date and time
  formats are now derived from a single setting, so the value written to a form and
  the value read back from it cannot disagree (:issues:`#826 <826>`).

* **SQL Server installations have their lost unique constraints restored.** On
  Microsoft SQL Server, ``mssql-django`` drops a unique index when an unrelated
  field change retypes a table's primary key, and does not put it back - which the
  4.0 migrations did to every table. The effect was silent: the database stopped
  enforcing 16 of the uniqueness rules QATrack+ declares, so duplicates could be
  created where the application intends one record, including
  ``TestListInstance.user_key``, whose purpose is to keep API submissions unique.
  This release puts them back.

  No other database engine was ever affected, and on those engines this step does
  nothing. If your database already contains duplicate rows, the affected index is
  reported and skipped rather than failing the upgrade - run ``python manage.py
  check_unique_constraints`` to list them, and the new ``qatrack.W011`` system check
  reports any constraint still unenforced (:issues:`#899 <899>`).

* **Users entitled to see every QC collection can see them again.** Seven querysets
  narrowed ``UnitTestCollection`` by ``visible_to__in=user.groups.all()``, and
  superuser status never entered the query - so a superuser belonging to no group
  matched nothing and the QA/QC selection windows came up **empty**. Only some
  windows went blank rather than all of them, which is what made it look like
  configuration rather than a defect. A non-superuser holding
  ``qa.can_review_non_visible_tli`` was in the same position, despite that
  permission existing for exactly this purpose. The narrowing still narrows: a user
  in the wrong group still sees nothing (:issues:`#883 <883>`).

* **The QC trees show every collection again.** Both the "Due & Overdue" frequency
  tree and the category tree collapsed repeated rows by the collection's *name*.
  The query returns a collection once per test it contains, so some collapsing is
  needed, but keying it on the name also removed a genuinely different collection
  whose name happened to match. Two collections called the same thing on one unit
  showed as one, with nothing to indicate the other existed. They are collapsed by
  identity now. The fix above is what made this reachable - narrowed to one group,
  two collections sharing a name rarely met (:issues:`#883 <883>`).

* **Test list memberships show the name of each test again.** The admin fetches
  each name over AJAX from an endpoint mounted beneath ``admin/``, and the admin
  site ends its own URLs with a catch-all that claimed the request first, so the
  admin answered its own endpoint with a 404 - for every user, including a
  superuser. A test list's memberships listed an id and a macro name and no test
  name, and a group permission could not fix it. The view and change icons beside
  the field now have a link as well; they were rendered without one and did nothing.
  A test saved with no name shows its id rather than nothing at all
  (:issues:`#897 <897>`).

* **``manage.py check`` reports calculation procedures that draw with
  ``matplotlib.pyplot``.** ``pyplot`` keeps its figures in state shared by
  everything in the same process, so two procedures plotting at the same time can
  take each other's figures - and QATrack+ cleared every figure in the process
  after a plot rather than only its own. The result was a plot saved against the
  wrong test, or an empty one, with nothing to indicate it.

  Whether a site can reach this depends on how it serves QATrack+: the Windows
  deployment serves requests from a thread pool sharing one process and is exposed,
  while the Linux and Docker deployments handle one request per process and are
  not. The new ``qatrack.W012`` system check names any procedure written this way
  and shows the ``UTILS.get_figure()`` form to replace it with, which returns a
  figure nothing else can reach. The documentation's own plotting example has been
  corrected - it previously showed the unsafe form.

* **Six fixes that had been written and then stranded are in.** Four were left on
  the unreleased 3.2.0 branch: a scheduled report to a group with no members raised
  ``AttributeError`` and was never sent; serializing QATrack+'s own ``JSONField``
  produced a Python repr rather than JSON, so a dumped ``AutoSave``,
  ``TestInstance.json_value`` or ``ServiceEvent.extra_info`` did not load back as a
  dictionary; AutoSave never loaded for Wrap Around tests, which ``set_value`` did
  not recognise as numerical; and the report preview threw on every window resize
  until its container had been laid out. The *Export Test Pack* and *Import Test
  Pack* links are also back on the Test and Test List Cycle changelists, where they
  had been left only on Test Lists, and string and date values in the QC history
  popover no longer render in black on a coloured label.

Other Changes
^^^^^^^^^^^^^

* **Dates are now shown as ``YYYY-MM-DD`` by default, in every language**, and the
  date pickers write back the same format they display. The entry for this, including
  the two settings that restore 4.0's appearance and what changes for a site with more
  than one language, is in the date and time fix above (:issues:`#826 <826>`).

* **The outstanding migrations have been recorded.** ``makemigrations`` reported 195
  pending field-state changes across seven apps on a clean checkout - all metadata,
  almost all of it ``verbose_name`` labels that the localisation work added to
  fields which had none without recording the resulting state. They are now one
  migration per app. Every operation is a no-op on SQLite, PostgreSQL and SQL
  Server, so applying them writes a row to ``django_migrations`` and changes no
  schema and no data. The effect is that ``manage.py makemigrations --check`` is
  meaningful again, having previously failed on every installation
  (:issues:`#896 <896>`).

* **The numpy names that numpy 2.0 removed are gone from the codebase**, and a test
  fails if another is added. ``np.NaN`` in the control chart's Gaussian fit would
  have raised ``AttributeError`` instead of returning a value, and ``np.float_`` in
  the JSON encoder was a redundant alias of ``np.float64``. QATrack+ still pins
  ``numpy<2.0``, so neither was reachable; clearing them now means a future move to
  numpy 2 is a change of pin rather than a change of pin plus a search for
  everything that accumulated behind it.

4.0.1
------

Bug Fixes
^^^^^^^^^

Ordered by consequence, most serious first.

* **``manage.py backup_site`` says when it has not backed up the database.** On MySQL,
  and on any engine it does not implement, it skipped the database without a word and
  finished as though it had written one, so a site could hold a set of backups
  containing no database at all. It now names the engine it cannot handle and skips
  the retention step rather than passing silently.

  **It still exits zero.** The command has no non-zero exit path, so a cron job or
  script that checks only the exit status cannot tell a complete backup from one with
  no database in it. Read its output, or check that a database file is present.
  Making it fail properly changes behaviour for anything already scheduled around
  it, so that is not in this patch release.

  It writes a database backup on **SQL Server and SQLite** only. PostgreSQL has never
  been among them - the command has always said so rather than failing quietly - so
  nothing changes for a PostgreSQL site, but one relying on this command does not
  have a database backup. Use ``pg_dump``, or the Docker backup script. There is an
  appendix in :ref:`qatrack_backup` for sites running SQLite in production.

* **PDF reports are complete again.** A report containing a forced page break
  silently lost everything after it, which affected the service log and fault
  reports, paper QC backup forms and test list instance details. The on-screen
  preview was unaffected, so the download appeared to be at fault rather than the
  report itself.

* **Service areas show their own names.** Every service area rendered as the words
  "service area" - in the admin, in every dropdown listing them, and anywhere a
  template showed one - so with more than one configured there was no way to tell
  them apart on screen.

* **The "Due & Overdue QC" page includes everything due today.** Its cutoff was
  midnight at the start of the day rather than the end of it, so an item that came
  due this morning did not appear until tomorrow, on the one page whose purpose is to
  show what is due. The Due Dates report was never affected and has always used the
  end of the day; the page now matches it.

* **Scheduled service event notices are sent again.** The periodic task was
  registered under a function name that does not exist, so it could never run
  (:issues:`#852 <852>`).

* **Report schedules can be created again.** Opening the schedule dialog for a report
  raised an ``AttributeError`` from ``ReportSchedule.__str__``, which read an
  ``rrule`` attribute that does not exist, so the schedule could not be saved. The
  translation catalogue is also loaded on the reports and charts pages, which
  previously fell back to untranslated strings (:issues:`#837 <837>`).

* **Report links no longer double the URL scheme.** A Site domain is documented as a
  bare host, but setting it to a full URL such as ``https://example.com`` is common,
  and the links in report bodies and the "View on site" header prepended the scheme a
  second time - producing ``http://https://example.com/...``, which a browser reads
  as the host ``https`` with the real host pushed into the path. Every such link was
  broken (:issues:`#853 <853>`).

* **Service event templates match return-to-service QC by intersection.** A template
  was excluded from a unit whenever it named any test list the unit was not assigned,
  rather than offering the ones it was, so a template could not be shared across
  machines or modalities (:issues:`#829 <829>`).

* **A fault type whose code has no ASCII form works.** Such a code produced an empty
  identifier, and its pages returned a 500 (:issues:`#677 <677>`).

* **String and string composite tests can be given a multiple choice tolerance
  again** (:issues:`#881 <881>`).

* **Composite and constant calculation procedures may use any Python the site runs
  on.** Procedures were checked against a syntax target fixed at Python 3.6 to 3.9,
  so ``match`` statements and ``type`` aliases were rejected on a site running 3.12.

* **Report PDFs load their stylesheets and logo on Windows.** Links were built by
  joining ``file://`` to a filesystem path, which on Windows turns the drive letter
  into a hostname, so none of a report's nine stylesheet and image links resolved and
  the PDF rendered unstyled and without the organisation logo.

* **Reports honour their paper size when a browser renders them.** A report set to A4
  was produced at Letter regardless.

* **The organisation logo sits in the top right of a report** rather than wrapping
  onto a second line below the heading.

* **A report's signature and date fields stay on one line** on A4 paper.

* **Report generation no longer leaves a partial PDF behind** when the browser fails
  part way through.

* **The schedule rule is readable in the report scheduling dialog** in dark mode,
  where it was white on white (:issues:`#837 <837>`).

* **Table controls on listing pages are translated.** *Showing x of y*, *Previous*,
  *Next*, *Search:* and *No data available* always rendered in English whatever
  language was active, because the tables' translated strings were never passed to
  DataTables (:issues:`#827 <827>`).

* **Client-side translations reach users who are not logged in.** The JavaScript
  translation catalogue was not exempt from the login requirement, so an anonymous
  visitor's request redirected to the login page, the browser parsed the HTML as
  JavaScript, and no client-side string was translated.

* **An intermittent JavaScript error on the QC overview, the parts reporting page and
  the unit available time page is gone.** Each used a scrollbar plugin without
  declaring it as a dependency, so whether it had loaded in time depended on what
  else a page happened to pull in first (:issues:`#822 <822>`).

Other Changes
^^^^^^^^^^^^^

* **Three ``Makefile`` targets that emptied application data have been removed:**
  ``clearct``, ``flushdb`` and ``__cleardb__``. Each acted on the database named by
  ``local_settings.py``, which in a clinical installation is the live one. Two were
  already broken and would have failed before doing damage; ``clearct`` worked. None
  is needed for any documented workflow, and ``make help`` advertised all three
  alongside the ordinary targets.

* **A sample data generator for development and debugging.**
  ``manage.py generate_sample_data`` builds a small site's worth of units, test lists
  and QC history, so a developer can reproduce behaviour that needs populated data
  without a copy of anyone's database.

* **The language a user selects persists.** The language cookie had no explicit
  lifetime, so it expired with the browser session and the interface reverted to the
  default language on the next visit.

Deployment and Upgrade Notes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Python 3.12 and Django 4.2.30 or newer are now required.** The Django floor was
  raised to pick up its security fixes, and Python is pinned to 3.12 - the version
  QATrack+ 4.0 is tested and deployed on.

* **The Docker backup script reads its database settings from the environment.**
  ``deploy/docker/backup/backup.sh`` previously hard-coded the database name and
  user. It now uses ``POSTGRES_DB``, ``POSTGRES_USER`` and ``POSTGRES_PASSWORD``, so a
  deployment that sets those in its Compose environment is backed up correctly, and
  one that does not will fail rather than dump the wrong database. Check your
  ``.env`` before relying on the next backup.

* **``CSRF_TRUSTED_ORIGINS`` can be set from the environment** for Docker
  deployments, falling back to ``ALLOWED_HOSTS`` when it is not given. See the notes
  in ``deploy/docker/.env.example``.

* **The ``installfixtures`` management command has been removed.** It loaded a
  fixture set that no longer matched the schema. Use ``manage.py loaddata`` with the
  fixtures you want.

* **The Windows upgrade guide has its service-setup section back** - the steps that
  register the QATrack+ service - which had gone missing.

4.0.0
------

QATrack+ 4.0.0 introduces a major platform modernization release focused on maintainability, deployment consistency, and long-term support readiness. This release includes updates to the Python and Django stack, Windows deployment tooling, and admin architecture.

Highlights
^^^^^^^^^^

* Localization support for multiple languages. Draft translations are available for English, French, and Spanish. 
* Upgraded core platform to newer Python and Django ecosystem components.
* Standardized environment and dependency management around uv.
* Improved Windows deployment workflow for both fresh installs and upgrades.
* Updated SQL Server guidance and local settings expectations for modern Django behavior.

Major Changes
^^^^^^^^^^^^^

* Windows deployment documentation has been refreshed for Server 2022 and SQL Server 2022 scenarios.
* Dependency and environment management now uses uv workflows for setup and synchronization.
* Windows service deployment is now fully automated via `install_winsw.ps1`, adopting a centralized WinSW wrapper (`qatrack-service.exe`) and simplifying the service name to `QATrack+ Web Service`.
* Local settings expectations now explicitly include host and CSRF origin configuration required by current Django versions.
* Database engine guidance for SQL Server has been updated to current backend conventions.

Technical Improvements
^^^^^^^^^^^^^^^^^^^^^^

* Removed external django-admin-views dependency and migrated related functionality into Django admin.
* Consolidated and simplified admin URL and view handling.
* Reduced package complexity by removing an unnecessary external dependency from the stack.
* Improved consistency of installation and upgrade command sequences.
* Updated time handling to use timezone-aware datetimes throughout the codebase.
* Added a `generate_sample_data` management command for development and testing. It fills a database with a small radiation oncology centre: two linacs and a CT simulator, TG-142 style daily and monthly QA protocols with references and tolerances, rolling QA history including an unreviewed backlog, service events with return to service QA, faults, a parts inventory, and saved reports with schedules. Re-running it extends the data rather than duplicating it, and the `--clear` option (which empties those tables for the whole database) asks for confirmation first. See the developers guide for the command's options and the sample logins.
* The development local settings template now enables `DEBUG` and sets `ALLOWED_HOSTS` for local addresses, and default fixture loading no longer depends on the current working directory.

Bug Fixes
^^^^^^^^^

* Service Event Templates can now be shared across different machines and modalities. When selecting a template, only the Return to Service tests that apply to the chosen unit will be added to the form (:issues:`#829 <829>`).
* Fixed an issue where resuming an autosaved QC session could display the wrong start date and time.
* Fixed tolerance compatibility validation across different test types.
* Fixed reference value type preservation in admin forms.
* Improved handling and messaging for incompatible tolerance and test-type combinations.
* Addressed multiple documentation inconsistencies and deployment workflow ambiguities.

Deployment and Upgrade Notes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Existing Windows v3.1 installations should follow the dedicated 4.0 upgrade guide.
* New installations should use the fresh install guide for uv-based environment setup.
* Verify service and task definitions after upgrade to ensure they point to the active virtual environment Python executable.
* Review local settings before first startup, including host and CSRF origin settings.

Acknowledgements
^^^^^^^^^^^^^^^^

Thank you to everyone who contributed bug reports, validation feedback, deployment testing, and documentation improvements that helped shape this release.

Contributors from the project history include:

* Cody Crewson (`@crcrewso <https://github.com/crcrewso>`_)
* Nathan Smela (`@NSmela <https://github.com/NSmela>`_)
* Ethan Sutherland (`@ETS1199 <https://github.com/ETS1199>`_)
* Matt Van Horn (`@mvanhorn <https://github.com/mvanhorn>`_)
* Vincent Leduc (`@leducvin <https://github.com/leducvin>`_)
* trugty (`@trugty <https://github.com/trugty>`_)



Earlier Series
~~~~~~~~~~~~~~

The notes for each earlier major series are kept as their own page rather than being
pulled into this one, so that this file only ever holds the series currently being
released.

.. toctree::
   :maxdepth: 1

   release_notes/v3.1
   release_notes/v0.3
   release_notes/v0.2
