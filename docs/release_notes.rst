Release Notes
=============

.. current series release notes will appear in this file,
   older release notes are included from the release_notes directory.
   when incrementing to a new series, the release notes for that series should be added here, and the release notes for the previous series should be moved to the release_notes directory.

.. _`release_notes_40`:

QATrack+ v4.0
~~~~~~~~~~~~~

.. _`release_notes_401`:

v4.0.1
------

A maintenance release. No database migrations, no configuration changes
required, and nothing user-facing changes shape - every item below is a fix
for something that was already wrong.

Bug Fixes
^^^^^^^^^

* Database backups on MySQL no longer skip the database itself.
  ``backup_site`` reported success while writing only the media archive
  (:issues:`857`).
* Service Event Templates are usable again on units whose Return to Service QC
  is not an exact superset of the template's. Matching is now by intersection,
  so a template shared between machines contributes only the tests that apply
  to the chosen unit (:issues:`829`).
* Report links no longer come out as ``http://https://…`` when the Site domain
  includes a scheme. Every "view record" link and the "View on site" link in
  report headers failed to resolve (:issues:`853`).
* The JavaScript translation catalogue is served to anonymous visitors again.
  It sits on every page, so signed-out users received the login page's HTML
  into a ``<script>`` tag and the client-side catalogue never loaded.
* Intermittent ``slimscroll is not a function`` errors on the QC overview,
  parts reporting and unit available time pages (:issues:`822`).
* The service-setup section missing from the Windows upgrade guide has been
  restored. Without it an upgrade completes and the site does not come back up.
* Report PDFs honour the paper size chosen for the report. Reports rendered
  through Chrome were always produced at Letter regardless of the setting.
* Long reports are no longer truncated at a page break.
* Date and time formats are configurable from a single setting and derived
  everywhere else, so the parser, the display, the date pickers and the field
  help text cannot disagree. Non-English locales no longer render a literal
  format key into the page, which had been blocking QC submission
  (:issues:`826`).

Documentation
^^^^^^^^^^^^^

* The Docker install instructions match ``deploy/docker/README.md`` again,
  including the ``USE_DOCKER`` setting the guide had never mentioned
  (:issues:`876`).
* The documentation builds without warnings. Thirty-odd malformed section
  underlines, a mistyped cross-reference role and a missing blank line before a
  target label were all silently degrading the rendered output.

Developer
^^^^^^^^^

* The Selenium suite runs headless on Firefox and Chromium, waits on conditions
  rather than fixed delays, and saves a screenshot of the page when a browser
  test fails. It also runs in CI for the first time.
* 99 tests that had never been collected now run, with a guard so that
  recurring is not silent.
* A ``poe`` task set provides the Makefile's targets on Windows, where ``make``
  is unavailable.
* The dead ``installfixtures`` management command has been removed; use
  ``loaddata`` as the installation guides describe (:issues:`877`).

v4.0.0
------

QATrack+ v4.0.0 introduces a major platform modernization release focused on maintainability, deployment consistency, and long-term support readiness. This release includes updates to the Python and Django stack, Windows deployment tooling, and admin architecture.

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

Bug Fixes
^^^^^^^^^

* Service Event Templates can now be shared across different machines and modalities. When selecting a template, only the Return to Service tests that apply to the chosen unit will be added to the form (:issues:`829`).
* Fixed an issue where resuming an autosaved QC session could display the wrong start date and time.
* Fixed tolerance compatibility validation across different test types.
* Fixed reference value type preservation in admin forms.
* Improved handling and messaging for incompatible tolerance and test-type combinations.
* Addressed multiple documentation inconsistencies and deployment workflow ambiguities.

Deployment and Upgrade Notes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Existing Windows v3.1 installations should follow the dedicated v4.0 upgrade guide.
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



QATrack+ v3.1
~~~~~~~~~~~~~

.. include:: release_notes/v3.1.rst


QATrack+ v0.3.0
~~~~~~~~~~~~~~~

.. include:: release_notes/v0.3.rst
