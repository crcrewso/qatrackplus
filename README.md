# Important Notice

This is an upgrade of the QATrack+ application running on Python 3.12.7 and Django 4.2.18 with MS SQL server (driver mssql), this is not a release version, only for testing. Initially tested with a blank database, but also with a restored database running on the the standard installation settings. This has only been tested for basic functionality, more in-depth testing is needed.

Instead of running pip install -r requirements\win.txt in the instructions run pip install -r requirements\reqs.txt.

The package django-admin-views needs updating but there is an error in the package https://github.com/koleror/django-admin-views/pull/43/commits/dffbc56f4f6b271c59c7e8bdc2036e8cbd5c4589.
Download the package here https://github.com/koleror/django-admin-views/tree/master and update the toml file as above.

Run python manage.py check, you may need to run python manage.py makemigrations and python manage.py migrate.

QATrack+ no longer has a maintainer. Please see the announcement on
the [QATrack+ Mailing List](https://groups.google.com/g/qatrack/c/79EoHF4U54Y)

If you are interested in taking over the project, please contact Randy Taylor
(randy@randlet.com).

# QATrack+
###### Copyright 2012 The Ottawa Hospital Cancer Center
---


QATrack+ is a fully configurable, free, and open source (MIT License) web
application for managing QA data for radiation therapy and medical imaging
equipment. QATrack+ is now used in many hospitals and clinics [around the
world](http://qatrackplus.com/#whos-using)! Visit the QATrack+ homepage at
http://qatrackplus.com

QATrack+ is deployable on most operating system/server/database platform
combinations. It was developed in the popular Python programming language using
the Django web framework so that QC data may be entered, reviewed, and analyzed
using a web browser.

The main features include:

* Ability to define QC tests via an user-friendly interface. Configuration
  settings are available for data type (Boolean, float, computational result,
  or multiple choice selection), test frequency (due/past due dates), reference
  values, and tolerance and action levels. Test configurations can be grouped
  and assigned to multiple units/devices to reduce configuration workload, and
  to simplify the configuration maintenance.
* Several options for trending numerical data via control charts and other
  tools. Data can be filtered by unit, date, or frequency, and can also be
  exported for external analysis.
* Support for multiple, unique user groups (e.g. administrators, physicists,
  assistants, therapists, etc) with user & group-specific privileges and test
  lists, as well as a configurable user authentication system.
* Easily integrate test procedures into data entry forms via embedded html
  or links to external documentation.
* Save incomplete work and complete it a later date.
* Configure a review/approval process with additional options for
  classifying data. The software also allows reviewers to easily differentiate
  between measurements performed as part of investigative work, or as part of
  routine QC testing.
* Integrated Service Log for tracking service events and machine downtime
* Parts tracker for tracking spare parts on hand, part costs and vendors
* Optional and configurable email notifications.
* The flexibility to host on an intranet or www, requiring minimal resources
  from IT departments. Can optionally be managed within a physics department if
  permitted by local institution policies.


## Documentation & Release Notes

The latest version is 3.1.1 Please review the
[release_notes](https://docs.qatrackplus.com/en/stable/release_notes.html)
before installing or upgrading.

The [documentation for versions 0.3.0+ can be found online](http://docs.qatrackplus.com)
and is where you should start if you are interested in installing or helping
develop QATrack+.

Documentation for earlier versions of QATrack+ (v0.2.7-v0.2.9) can be found in
the [QATrack+ Wiki on BitBucket](https://bitbucket.org/tohccmedphys/qatrackplus/wiki/Home).

---

## Important notes regarding 3rd party code in QATrack+

QATrack+ relies on a number of open source projects, many of which are
distributed along with QATrack+; licenses covering their usage and modification
are either included along with the source code files or embeded directly in the
source (or a url where you can find it).
