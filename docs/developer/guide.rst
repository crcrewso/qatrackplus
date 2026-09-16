Developers Guide
================

.. note::

    **Disclaimer**: This guide was developed and tested on Ubuntu Linux. 
    While the instructions should work on other operating systems, some commands, package names, 
    or installation steps may differ. If you encounter issues on a different OS, please refer 
    to the specific documentation for your platform or reach out to the community for assistance.

.. toctree::
   :maxdepth: 3
   :caption: Developers Guide Contents:

   self
   schema


Installing QATrack+ For Development
-----------------------------------

Due to the huge volume of tutorials already written on developing software
using Python, Django, and git, only a brief high level overview of getting
started developing for the QATrack+ project will be given here.  That said,
there are lots of steps involved which can be intimidating to newcomers
(especially git!).  Try not to get discouraged and if you get stuck on anything
or have questions about using git or contributing code then please post to the
:mailinglist:`mailing list <>` so we can help you out!

Prerequisites
~~~~~~~~~~~~~

QATrack+ is developed using Python 3.12. We recommend using the latest stable
version of Python 3.12 for the best development experience and compatibility.

Node.js (Frontend)
~~~~~~~~~~~~~~~~~~

QATrack+ includes a Vue 3 frontend bundle compiled with Vite. Node.js 22 or newer
is required to build it locally. The compiled file is **not** committed to the
repository — release archives include a pre-built copy so deployers have no Node.js
requirement. If you are developing from a ``git clone`` you must build it yourself
(see :ref:`building-frontend` below).

Git
~~~

QATrack+ uses the git version control system. While it is possible to download
and modify QATrack+ without git, if you want to contribute code back to the
QATrack+ project, or keep track of your changes, you will need to learn about
git.

You can download and install git from https://git-scm.com. After you have git
installed it is recommended you go through a git tutorial to learn about git
branches, commiting code and pull requests. There are many tutorials available
online including a `tutorial by the Django team
<https://dont-be-afraid-to-commit.readthedocs.io/en/latest/>`__ as well as
a tutorial on `GitHub <https://try.github.io/>`__.

.. _forking-repo:

GitHub Account
~~~~~~~~~~~~~~

The QATrack+ project currently uses `GitHub <https://github.com>`__ for
hosting its source code repository. To contribute code to QATrack+
you will need to create a fork of QATrack+ on GitHub, make your changes,
then make a pull request to the main QATrack+ project.

Creating a fork of QATrack+ is explained in the `GitHub documentation
<https://guides.github.com/activities/forking/>`__.

uv Package Manager
~~~~~~~~~~~~~~~~~~~

The QATrack+ project uses `uv <https://docs.astral.sh/uv/>`__, a fast Python
package manager. uv handles Python version management, virtual environments,
and dependency management.

Install uv using the official installer (recommended):

.. code-block:: shell

    # On Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh

.. code-block:: shell

    # Alternative method using pip
    pip install uv

For other installation methods or troubleshooting, see the full installation guide at https://docs.astral.sh/uv/getting-started/installation/

Setting up your development environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First create a :ref:`fork <forking-repo>` of the QATrack+ repository on GitHub.

Then clone your fork to your local machine:

.. code-block:: shell

    git clone https://github.com/YOUR_USERNAME/qatrackplus.git
.. _building-frontend:

Building the Frontend
~~~~~~~~~~~~~~~~~~~~~

The compiled Vue frontend bundle (``qatrack/qatrack_core/static/dist/faults.js``)
is **not** tracked in version control. Release archives ship with a pre-built copy,
but developers working from a ``git clone`` must generate it manually.

After cloning (and whenever source files under ``qatrack/faults/static/faults/src/``
change), run:

.. code-block:: shell

    npm ci          # install dependencies (once, or after package.json changes)
    npm run build   # compile faults.js into qatrack/qatrack_core/static/dist/

.. note::

    The generated ``faults.js`` file is gitignored — do **not** commit it.

Selecting an Editor or IDE
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use a variety of tools to edit and work on the QATrack+ codebase. Some popular options include:

- **VS Code**: A free, open-source editor with Python and Django support.
- **Cursor**: An AI-powered code editor that integrates with GitHub Copilot and other AI tools.
- **PyCharm**: A Python IDE with advanced Django support.
- **Vim/Neovim**: Lightweight, keyboard-driven editors.
- **Emacs**: Highly customizable editor.

Choose the editor or IDE that best fits your workflow. All you need is a text editor and a terminal to get started!

Creating a Virtual Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have decided on a text editor or IDE, create a virtual environment with Python 3.12 using uv:

.. code-block:: shell

    # Create virtual environment with Python 3.12
    uv venv --python 3.12

    # Activate the virtual environment (Linux/macOS):
    source .venv/bin/activate

On Windows, activate it from PowerShell instead:

.. code-block:: powershell

    .\.venv\Scripts\Activate.ps1

Install development dependencies:

.. code-block:: shell

    # Install all development dependencies
    uv sync --dev

.. note::

    Activating the virtual environment is optional. ``uv sync`` creates and
    manages ``.venv`` for you, and prefixing a command with ``uv run`` (e.g.
    ``uv run pytest``) runs it inside that environment without activation.
    The examples below use the bare ``python``/``pytest`` form, which assumes
    you have activated it; add ``uv run`` in front of each if you would
    rather not. ``AGENTS.md`` and ``CONTRIBUTING.md`` in the repository root
    use the ``uv run`` form throughout.



Creating your development database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rather than using a full blown database server for development work, You can
use Sqlite3 which is included with Python.

Once you have the requirements installed, copy the debug `local_settings.py` and `local_test_settings.py`
files from the deploy subdirectory and then create your database:

.. code-block:: shell

    cp deploy/dev/local_settings.dev.py qatrack/local_settings.py
    cp deploy/dev/local_test_settings.sqlite.py qatrack/local_test_settings.py
    mkdir db
    python manage.py migrate
    python manage.py createcachetable


this will put a database called `default.db` in the `db` subdirectory.
``deploy/dev/`` also has ``local_test_settings.memory.py``/``postgres.py``/
``mysql.py``/``mssql.py`` templates if you'd rather test against a
different engine - see `Running The Test Suite`_ below for
``make test-<engine>``, which runs the suite against one of these without
touching your usual ``local_test_settings.py``.

.. _local_settings_templates:

``local_settings.py`` templates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``deploy/dev/local_settings.dev.py`` above is the right starting point for
development work. The remaining ``local_settings.py`` templates under
``deploy/`` target real deployments rather than development, and are the
ones referred to by the error QATrack+ raises when ``qatrack/local_settings.py``
is missing:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Template
     - Use it for
   * - ``deploy/dev/local_settings.dev.py``
     - Local development (sqlite, ``DEBUG`` on). Start here.
   * - ``deploy/sqlite/local_settings.py``
     - A file-backed sqlite deployment.
   * - ``deploy/postgres/local_settings.py``
     - A PostgreSQL deployment (see also the ``.sql`` role/database setup
       scripts alongside it).
   * - ``deploy/mysql/local_settings.py``
     - A MySQL/MariaDB deployment (likewise with ``.sql`` setup scripts).
   * - ``deploy/win/local_settings.py``
     - A Windows/MS SQL Server deployment.

Copy whichever one matches your target to ``qatrack/local_settings.py`` and
edit it from there. For full deployment instructions see the
:doc:`installation guides </install/install>`, not this page.


Understanding the Settings Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

QATrack+ uses a layered approach to Django settings, with each file serving a specific purpose. Understanding this hierarchy will help you configure your development and testing environment.

Every file below is imported with ``from ... import *``, so the *last* one
loaded wins for any given setting. Under a test run the chain is
``settings.py`` -> ``local_settings.py`` -> ``test_settings.py`` ->
``local_test_settings.py``, giving this order:

**Settings File Hierarchy (Highest to Lowest Precedence):**

1. ``local_test_settings.py`` - Your custom test environment overrides

   - Contains all essential development and test settings in one place
   - This is the main file you'll customize for your testing needs

2. ``test_settings.py`` - Default test environment settings

   - Contains test-specific defaults like password hashers and notification
     settings
   - Note that ``test_settings.py`` re-imports ``local_settings.py`` and
     *then* applies its own values, so under a test run it overrides
     anything you set in ``local_settings.py``. If you set, say,
     ``LANGUAGE_CODE`` or ``NOTIFICATIONS_ON`` in ``local_settings.py`` and
     wonder why the tests don't see it, this is why - put test-only values
     in ``local_test_settings.py`` instead.

3. ``local_settings.py`` - Your custom development environment overrides

   - Contains development-specific settings like database configuration
   - This is the file the development server and management commands use;
     outside of a test run it is the highest-precedence file.

4. ``settings.py`` - Base Django application settings

   - Contains core Django configuration, installed apps, middleware, etc.

Collect Static Files
~~~~~~~~~~~~~~~~~~~~

Before running the development server, you need to collect all static files to the STATIC_ROOT directory:

.. code-block:: shell

    python manage.py collectstatic --noinput


Loading Default Data (Fixtures)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

QATrack+ comes with pre-configured default data that provides a foundation for development and testing. This includes common QA categories, test frequencies, modalities, vendors, and other essential data structures.

To load the default data into your development database:

.. code-block:: shell

    python manage.py loaddata fixtures/defaults/*/*.json

This command will populate your database all default data.

You can also load specific fixture categories individually if you only need certain data:

.. code-block:: shell

    # Load only QA-related fixtures
    python manage.py loaddata fixtures/defaults/qa/*.json

    # Load only unit-related fixtures
    python manage.py loaddata fixtures/defaults/units/*.json

    # Load only service log fixtures
    python manage.py loaddata fixtures/defaults/service_log/*.json

Running the development server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After the database is created, create a super user so you can log into QATrack+:

.. code-block:: shell

    python manage.py createsuperuser

and then run the development server:

.. code-block:: shell

    python manage.py runserver 

Once the development server is running you should be able to visit
http://127.0.0.1:8000/ in your browser and log into QATrack+.

Next Steps
~~~~~~~~~~

Now that you have the development server running, you are ready to begin
modifying the code!  If you have never used Django before it is highly
recommended that you go through the official `Django tutorial
<https://docs.djangoproject.com/en/4.2/intro/tutorial01/>`__ which is an
excellent introduction to writing Django applications.

Once you are happy with your modifications, commit them to your source code
repository, push your changes back to your online repository and make a pull
request! If those terms mean nothing to you...read a git tutorial!


QATrack+ Development Guidelines
-------------------------------

The following lists some guidelines to keep in mind when developing for
QATrack+.


Internationalization & Translation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please mark all strings and templates in QATrack+ for translation. This will
allow for QATrack+ to be made available in multiple languages. Note that
translatable labels for form fields (i.e. `my_form_field = FieldClass(label=_l("the_label"), ...)`)
and translatable verbose names for model fields (i.e. `my_model_field = ModelClass(verbose_name=_l("the_verbose_name"), ...)`)
are often required for the rendering of translated strings in the frontend, so
the recommendation, as stated in the Django docs, is to always include them.

For discussion
of how to mark templates and strings for translation please read the `Django
docs on translation
<https://docs.djangoproject.com/en/4.2/topics/i18n/translation/>`__.

**Adding a New Language to QATrack+**

For detailed instructions on adding a new language to QATrack+, including step-by-step
workflows and translation automation, please refer to the :ref:`Add Language Tutorial <add_language>` 
in the tutorials section.


Tool Tips And User Hints
~~~~~~~~~~~~~~~~~~~~~~~~

Where possible all links, buttons and other "actionable" items should have a
tooltip (via a `title` attribute or using one of the bootstrap tool tip
libraries) which provides a concise description of what clicking the item will
do. For example:

.. code-block:: html

    <a class="..."
        title="Click this link to perform XYZ"
        href="..."
    >
        Foo
    </a>

Other areas where tooltips are very useful is e.g. badges and labels where
wording is abbreviated for display. For example:

.. code-block:: html

    <i class="fa fa-badge" title="There are 7 widgets for review">7<i>

    <span title="This X has Y and Z for T">Foo baz qux</span>



Formatting & Style Guide
------------------------

General formatting
~~~~~~~~~~~~~~~~~~

QATrack+ uses `ruff <https://docs.astral.sh/ruff/>`__ for linting,
formatting, and import ordering - it replaces the older flake8/yapf/isort
combination entirely, and their config sections have been removed from
``setup.cfg`` (the file itself has been removed - ruff's configuration lives
under ``[tool.ruff]`` in ``pyproject.toml``). Quote style is **single
quotes**, and import ordering is enforced via ruff's ``I`` rule set - no
separate isort pass needed.

``line-length`` is set to **120 characters**, but note that ``E501``
(line-too-long) is in the ``ignore`` list, so ``ruff check`` will *not*
flag an over-long line. 120 is the target ``ruff format`` wraps to, and
until repo-wide formatting has been applied (see below) it is a convention
to aim for rather than something the linter enforces.

To check for violations:

.. code-block:: shell

    uv run ruff check .

Repo-wide ``ruff format`` hasn't been applied to this codebase yet, so avoid
running it across everything - that would surface a large, unrelated
reformatting diff. Scope it to the files you actually changed:

.. code-block:: shell

    uv run ruff format <files you changed>

Before opening a PR, also run the full pre-commit suite (ruff lint plus
``django-upgrade``):

.. code-block:: shell

    uv run pre-commit run --all-files

Using Make Commands
~~~~~~~~~~~~~~~~~~~

QATrack+ includes a Makefile with convenient shortcuts for common development tasks like running tests, formatting code, and building documentation. You can see all available commands by running:

.. code-block:: shell

    make help

For detailed information about using make and understanding Makefiles, refer to the `GNU Make Manual <https://www.gnu.org/software/make/manual/>`_.

Import Order
~~~~~~~~~~~~

Imports should be split into three sections - standard library, third
party, and QATrack+ specific - each in alphabetical order. ``ruff check .``
enforces this automatically (rule set ``I``), so there's no separate tool to
run or configure; ``ruff`` will flag anything out of order and, in most
cases, ``uv run ruff check . --fix`` will reorder it for you.

Indentation
~~~~~~~~~~~

Python code for QATrack+ use 4 spaces for indentation. Django templates (and
other html files) should use 2 spaces for indentation.  Javascript code should
use 4 spaces for indentation.


Setting Up Selenium Browser Testing
-----------------------------------

QATrack+ includes Selenium tests that simulate user interactions with the web interface and are marked with the `@pytest.mark.selenium` decorator.

**Browser Requirements**

You need a browser installed - either Firefox or Chrome/Chromium, whichever
you prefer. You do **not** need to separately install or configure a
matching driver (geckodriver/chromedriver): Selenium Manager, built into
Selenium 4.6+, detects whichever browser you have installed and downloads a
matching driver automatically the first time a Selenium test runs. This
works the same on a workstation, a bare CI runner, or an agent sandbox - no
display server (X11/Wayland/Xvfb) is needed either, since tests run the
browser in its own native headless mode by default.

.. code-block:: shell

    # Install whichever browser you don't already have
    sudo apt install firefox
    # - or -
    sudo apt install chromium

**Configuring Selenium Tests**

Set `SELENIUM_BROWSER` in `qatrack/local_test_settings.py` to pick which
browser drives the tests:

.. code-block:: python

    SELENIUM_BROWSER = 'firefox'   # the default
    # SELENIUM_BROWSER = 'chromium'

That's the only setting most people need. A couple of others (all defined
in `qatrack/settings.py`, overridable the same way) are there if you need
them:

* `SELENIUM_HEADLESS` - `True` by default (native headless mode, no display
  needed). Set to `False`, on a machine with a real display, to watch a
  test execute in a visible browser window - useful when debugging a
  failing Selenium test.
* `SELENIUM_FIREFOX_DRIVER_PATH` / `SELENIUM_CHROMIUM_DRIVER_PATH` - only
  needed if you want to pin a specific driver binary instead of letting
  Selenium Manager resolve one automatically.

Both `SELENIUM_BROWSER` and `SELENIUM_HEADLESS` can also be set from the
command line for a single run, instead of edited into a settings file -
useful for a one-off ("just this run, watch it in Chromium instead"):

.. code-block:: shell

    SELENIUM_BROWSER=chromium SELENIUM_HEADLESS=False pytest --run-selenium

Both values are single words, so neither needs quoting on any shell.


Running The Test Suite
----------------------

Once you have QATrack+ and its dependencies installed (and optionally configured
Selenium browser testing above), you can run the test suite from the root
QATrack+ directory using the `pytest` command (configuration lives under
``[tool.pytest.ini_options]`` in ``pyproject.toml``):


.. code-block:: sh

    ./qatrackplus> pytest
    ...
    qatrack/accounts/tests/test_accounts.py ✓✓✓

**Running Different Types of Tests**

Selenium (GUI/browser) tests are skipped by default - a plain `pytest` run
covers everything else, faster and without needing a browser installed:

.. code-block:: shell

    pytest

Run everything, including Selenium tests:

.. code-block:: shell

    pytest --run-selenium

Run *only* the Selenium tests:

.. code-block:: shell

    pytest -m selenium

`--run-selenium` and `-m selenium` both work - use whichever reads more
naturally for what you're doing.

.. deprecated:: 4.0

    The older `pytest -m "not selenium"`, to exclude the GUI tests
    explicitly, still works - it needs quoting on every shell for no
    benefit now that plain `pytest` does the same thing with nothing to
    type at all. It emits a ``PytestDeprecationWarning`` and will be
    removed in QATrack+ 4.2; switch to plain `pytest`.

To test against a specific database engine without disturbing whatever
``qatrack/local_test_settings.py`` you normally use day to day:

.. code-block:: shell

    make test-sqlite
    make test-memory
    make test-postgres
    make test-mysql
    make test-mssql

Each requires ``qatrack/local_test_settings.<engine>.py`` to already exist -
create it from the matching ``deploy/dev/local_test_settings.<engine>.py``
template first. The target swaps that file in for the run and restores your
previous ``local_test_settings.py`` afterward regardless of whether the
tests passed.

``make test-integration`` goes a step further: provisions a brand-new
sqlite database exactly the way a fresh deployment would (``migrate``,
``createcachetable``, ``collectstatic``, ``createsuperuser``) and runs the
suite with ``--reuse-db`` directly against it, so the whole deployment
sequence is exercised for real rather than just a disposable test database.

For more information on using pytest, refer to the `pytest documentation
<https://pytest.org>`__.

.. important::

    All new code you write should have tests written for it.  Any non trivial code
    you wish to contribute back to QATrack+ will require you to write tests
    for the code providing as high a code coverage as possible.  You can measure code coverage
    in the following way:

    .. code-block:: shell

        make cover


Areas with no test coverage
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some parts of QATrack+ are not covered by the suite, and cannot currently be
covered without work that has not been done yet. They are listed here so
that a gap is not mistaken for "this is tested and passing".

**LDAP / Active Directory authentication.** QATrack+ supports authenticating
against LDAP and Active Directory through the ``AD_LDAP_*`` settings in
``qatrack/settings.py`` (see :doc:`/install/authentication_backends` for how
to configure it), and this is how a large share of clinical deployments log
their users in. There is **no test coverage for any of it**, anywhere in the
suite, and no supported way to exercise it:

* no fixtures or mock directory,
* no containerised directory server for local development,
* nothing in CI - the ``ldap`` extra is not installed in any CI job, so the
  three tests in ``qatrack/accounts/tests/test_accounts.py`` that need the
  ``ldap`` module are skipped rather than run,
* no documented manual test procedure.

In practice this means a change to the authentication backends can only be
verified by hand, against a real directory server that a contributor must
supply themselves. Treat changes in that area with corresponding caution,
and say so explicitly in the pull request.

The likely shape of a fix, if someone takes it on, is a docker-compose
service running a directory server (``osixia/openldap`` or similar) plus a
matching ``local_test_settings`` template, mirroring how the per-engine
database templates under ``deploy/dev/`` already work. That would also let
CI install the ``ldap`` extra and actually run those three skipped tests.


Notes on running the Selenium tests in parallel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Not implemented - recorded here so the groundwork is not re-derived.

The suite runs serially and takes roughly nine minutes locally. ``pytest-xdist``
would parallelise it, and the architecture is more amenable than it looks,
largely because the tests now run headless:

* **Database** - each xdist worker is a separate process, and pytest-django
  gives each its own test database. The in-memory SQLite used in CI is
  naturally per-process.
* **Live server port** - ``LiveServerTestCase`` already binds a free port per
  instance.
* **The single-threaded server** - ``LiveServerSingleThread`` constrains
  concurrency *within* one server, not across processes, so it is not a
  blocker.
* **Display contention** - this is the one headless genuinely solves.
  Visible browsers compete for focus and window placement, which makes them
  effectively unparallelisable; headless browsers have neither.

The real blocker is shared filesystem state: media and upload directories,
and any file-backed database path, would collide between workers and need
per-worker temporary directories.

``--dist loadscope`` is the distribution mode to use, so all tests in a class
stay on one worker and match the existing per-class browser lifecycle.

**Sequencing matters.** The remaining ``time.sleep()`` calls should be
replaced with proper waits *before* any of this is attempted. Parallelism
multiplies flakiness rather than curing it, and the Chromium timing flakes
documented in ``setUpClass`` would become considerably harder to diagnose
spread across several workers.


Customizing Organization Logos
------------------------------

QATrack+ reports include an option to display your organization's logo.

**Adding Your Organization Logo**

1. **Prepare your logo file:**
   - Use a PNG format for best compatibility
   - Recommended size: 200x60 pixels or similar aspect ratio
   - Keep file size reasonable (under 100KB)

2. **Replace the placeholder logo:**
   - Navigate to ``qatrack/reports/static/reports/img/``
   - Replace the existing ``logo.png`` file with your own logo
   - Keep the same filename (``logo.png``) to avoid template changes

3. **Alternative: Use a different filename:**
   - If you prefer a different filename, edit ``qatrack/reports/templates/reports/_header.html``
   - Update all references from ``logo.png`` to your preferred filename
   - Update the alt text and fallback messages as needed

4. **Collect static files:**
   After making changes, run:
   
   .. code-block:: shell
   
       python manage.py collectstatic --noinput

**Logo Display Options**

- **HTML Reports:** Logo is displayed using Django's static file handling
- **PDF Reports:** Logo uses file:// paths for compatibility with PDF generation
- **Error Handling:** If the logo fails to load, nothing is displayed (no fallback message)
- **Visibility Control:** Users can toggle logo display on/off in report settings

**Customizing Logo Text**

To change the alt text:
- Edit ``qatrack/reports/templates/reports/_header.html``
- Update the translation strings for "Organization Logo"
- Add translations to your locale files if using multiple languages

**Note:** The logo functionality is designed to be easily customizable without requiring code changes to the core application.


Writing Documentation
~~~~~~~~~~~~~~~~~~~~~

As well as writing tests for your new code, it will be extremely helpful for
you to include documenation for the features you have built.  The documentation
for QATrack+ is located in the `docs/` folder and is seperated into the
following sections:

#. **User guide:** Documentation for normal users of the QATrack+ installation.

#. **Admin guide:** Documentation for users of QATrack+ who are responsible for
   configuring and maintaining Test Lists, Units etc.

#. **Tutorials:**  Complete examples of how to make use of QATrack+ features.

#. **Install:** Documentation for the people responsible for installing,
   upgrading, and otherwise maintaining the QATrack+ server.

#. **Developers guide:** You are reading it :)

Please browse through the docs and decide where is the most appropriate place
to document your new feature.

While writing documentation, you can view the documentation locally in your web
browser (at http://127.0.0.1:8008 by default) by running one of the following
commands:

.. code-block:: shell

    make docs-autobuild
    # -or-, to use a different port (e.g. because 8008 is already taken):
    make docs-autobuild port=8010
    # -or-, without the Makefile at all:
    sphinx-autobuild docs docs/_build/html --port 8008


Version Naming Convention
~~~~~~~~~~~~~~~~~~~~~~~~~

QATrack+ uses **Eff Ver (Effort Versioning)** for its version naming convention. 
Eff Ver is a versioning strategy that focuses on the effort required to upgrade 
rather than semantic meaning. This approach prioritizes the practical impact on 
users and developers when considering version changes.

For more information about Eff Ver, see the `Eff Ver documentation 
<https://effver.org>`__.

**Version Number Structure**

The version number follows the format `X.Y.Z` where:

- **X (Major)**: Corresponds to the Django LTS release version
  - Currently at 4.0.0 (Django 4.2 LTS)
  - When upgrading to Django 5.2 LTS, version will become 5.0.0
  - This ensures compatibility and upgrade path alignment with Django

- **Y (Minor)**: Feature releases within the same Django LTS cycle
- **Z (Patch)**: Bug fixes and minor improvements

**Examples:**
- 4.0.0: Initial release on Django 4.2 LTS
- 4.1.0: Major feature release while staying on Django 4.2 LTS
- 4.1.1: Bug fix release
- 5.0.0: Upgrade to Django 5.2 LTS


Copyright & Licensing
---------------------

The author of the code (or potentially their employer) retains the copyright of
their work even when contributing code to QATrack+.  However, unless specified
otherwise, by submitting code to the QATrack+ project you agree to have it
distributed using the same `Apache License, Version 2.0
<https://github.com/qatrackplus/qatrackplus/blob/develop/LICENSE>`__ as
QATrack+ uses (as of version 4.0 - earlier releases were MIT-licensed).


I'm not a developer, how can I help out?
----------------------------------------

Not everyone has development experience or the desire to contribute code to
QATrack+ but still wants to help the project out.  Here are a couple of ways
that you can contribute to the QATrack+ project without doing any software
development:


* **Translations:** QATrack+ supports multiple languages through its
  internationalization infrastructure. We welcome community contributions for
  translation files in different languages. Use the translation manager script
  to help automate translations, then refine them manually for accuracy.
  See the "Internationalization & Translation" section above for detailed commands.

* **Tutorials:** :ref:`Tutorials <tutorials>` are a great way for newcomers to
  learn their way around QATrack+.  If you have an idea for a tutorial, we
  would love to include it in our tutorials section!

* **Mailing List:** QATrack+ has a :mailinglist:`mailing list <>` which
  QATrack+ users and administrators may find useful for getting support and
  discussing bugs and/or features. Join the list and chime in!

* **Spread the word:** The QATrack+ community has grown primarily through word
  of mouth. Please let others know about QATrack+ when discussing QA/QC
  software :)

* **Other:** Have any ideas for acquiring development funding for the QATrack+
  project?  We'd love to hear them!
