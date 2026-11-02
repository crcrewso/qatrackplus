# Security policy

QATrack+ runs in hospital physics departments, on servers that hold the records
behind treatment-machine QA. We want to hear about anything that could put those
records, or the people who rely on them, at risk, and we are grateful to anyone
who takes the time to tell us.

## Reporting a vulnerability

Please don't report a security problem in a public GitHub issue, in Discussions
or on the Google Group; those are read by everyone. Instead, email
**[medphys@crcrewso.ca](mailto:medphys@crcrewso.ca)** with "QATrack+ security"
in the subject line.

Email is how reports reach us today. A more sustainable mechanism will follow,
and this page will be updated when it does.

Tell us what you found, the QATrack+ version you found it in (*Admin › About*),
how to reproduce it, and what you think the impact is. A rough description is
enough to start; we would rather hear early than late, and we are happy to work
out the details together.

**Please never include patient or clinical data in a report.** Describe the
shape of a record rather than its contents, and remove anything that could
identify a person or a site.

## What to expect

We will answer every report, and we will always tell you what we decided and
why.

- We will acknowledge your report within **7 days**.
- QATrack+ is built for a trusted internal network and is maintained by
  volunteers, so we weigh each report by what someone already inside that
  network could do with it.
- Some reports become a fix in the next patch release; some wait for the next
  feature release; and some become a documented known limitation, with advice
  for site administrators, on the [Security page](docs/security.rst) of the
  documentation.
- Whichever it is, you will hear it from us directly, and we will credit you in
  the release notes if you would like us to.

A report we cannot fix soon is still a report we are glad to have: it lets every
site decide for itself what to do.

## Supported versions

| Version | Security fixes |
|---|---|
| 4.0.x (`releases/4.0`) | Yes |
| `develop` | Yes |
| 3.1 and earlier | No. Please upgrade; the install guides have an upgrade path |

## Deployment assumptions

QATrack+ is designed for a trusted internal network and should not be exposed
directly to the internet. The install guides say which settings a site
administrator is responsible for (`ALLOWED_HOSTS`, `SECRET_KEY`, HTTPS, LDAP
certificates). A report that a *documented* configuration is unsafe is a
vulnerability report. A site that has not followed the guide is a support
question, and welcome in Discussions.

## Code scanning

This repository runs GitHub CodeQL on its Python and JavaScript. Its findings
are triaged like any other report.
