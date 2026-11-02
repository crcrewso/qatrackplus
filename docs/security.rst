.. _security:

Security
========

QATrack+ is designed for a trusted internal network, and holds the records
behind treatment-machine QA. This page is for site administrators, and for
anyone who has found a security problem. It says how to report one, how reports
are sorted, and which limitations are known.

.. _security_reporting:

Reporting a problem
-------------------

Please don't report a security problem in a public GitHub issue, in Discussions
or on the Google Group; those are read by everyone. Instead, email
`medphys@crcrewso.ca <mailto:medphys@crcrewso.ca>`__ with "QATrack+ security"
in the subject line. Email is how reports reach us today; a more sustainable
mechanism will follow, and this page will say so when it does.

Tell us what you found, the QATrack+ version (*Admin › About*), how to
reproduce it, and what you think the impact is. A rough description is enough
to start. **Please never include patient or clinical data in a report**:
describe the shape of a record rather than its contents, and remove anything
that could identify a person or a site.

We will acknowledge your report within 7 days, and we will always tell you what
we decided and why. The ``SECURITY.md`` file at the root of the repository says
the same, in the place GitHub looks for it.

.. _security_triage:

How reports are sorted
----------------------

QATrack+ is maintained by volunteers, so we weigh each report by what someone
already inside your network could do with it. Every report lands in one of three
places, and the reporter hears which, and why:

* **A fix in the next patch release.** The problem can be reached by someone
  who is not signed in, or by an ordinary user, from inside the network; or it
  affects the integrity of QC records, reviews or sign-offs.
* **A fix in the next feature release.** Exploiting it needs an administrator
  account, or a configuration the install guides don't recommend.
* **A documented known limitation.** The problem comes with the deployment
  model itself. It is listed below with advice for site administrators, so each
  site can decide for itself, and it is credited to the reporter if they wish.

A report we cannot fix soon is still a report we are glad to have.

.. _security_assumptions:

What a site is responsible for
------------------------------

QATrack+ should not be exposed directly to the internet. The install guides say
which settings a site administrator is responsible for: the host list and
secret key in :ref:`the settings reference <qatrack-config>`, and for Docker
sites :ref:`HTTPS <docker_https>`, :ref:`the secret key <docker_secret_key>`
and :ref:`LDAPS certificates <docker_ldaps>`. A report that a *documented*
configuration is unsafe is a vulnerability report. A site that has not followed
the guide is a support question, and welcome in Discussions.

.. _security_known_limitations:

Known limitations
-----------------

Entries are added here when a report is accepted as a known limitation, after
the reporter has been told. Each one says what the limitation is, who it
affects, what a site can do about it, and when it was recorded.

Nothing is listed yet.
