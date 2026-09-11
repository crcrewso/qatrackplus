:orphan:

Docker backup mechanism: evaluation
====================================

This is a point-in-time engineering evaluation of the Docker deployment's
backup mechanism, written while fixing the `pg_restore` version-mismatch bug
tracked on the `docker-backup-restore` branch. It records what the current
mechanism does, what's genuinely wrong with it, what was considered as a
replacement, and what was actually changed versus what's left as a documented
recommendation for a deployer/maintainer decision.

Current mechanism
------------------

A dedicated `backup` service (`deploy/docker/compose.yaml`) runs continuously
alongside the rest of the stack. Inside it, `dcron` fires `backup.sh` once a
day at 2 AM, independent of `docker-compose up`/`down`. Each run:

* Dumps the database once with `pg_dump -F c` (PostgreSQL's custom archive
  format - compressed, and restorable selectively with `pg_restore`) and
  tars the media volume once with `tar -czf`.
* Copies that single daily snapshot into whichever of three retention tiers
  apply today - `daily` always, plus `weekly`/`monthly` on their configured
  trigger day - rather than re-dumping per tier.
* Ages each tier out independently on its own window
  (`BACKUP_DAYS_TO_KEEP`/`BACKUP_WEEKS_TO_KEEP`/`BACKUP_MONTHS_TO_KEEP`),
  matching `manage.py backup_site`'s daily/weekly/monthly scheme (see
  "Bugs found" below - this replaced an original flat 7-day window that
  applied to every backup regardless of tier).

Both kinds of file land in `deploy/docker/backups` on the Docker host itself
(a bind mount, not a named volume - `./backups:/backups` in `compose.yaml`).

This is architecturally reasonable for the project's actual deployment model
(self-hosted `docker-compose` on a single host, run by clinic IT staff who
are not necessarily database administrators) - it needs no external services,
no cloud credentials, and produces backups a human can inspect and move
around as plain files. The problems found are in the *implementation*, not
the *approach*.

Bugs found
----------

**`pg_restore` version mismatch (fixed on this branch).** The `backup`
image's Dockerfile installed Alpine's `postgresql-client` meta-package,
which resolves to whatever the latest packaged client is (16.x, as of
writing) - a different major version than the `postgres:15-alpine` image the
`postgres` service actually runs. PostgreSQL's custom-format archives embed
a version tag in their header, and older `pg_restore` binaries refuse to read
archives written by a newer `pg_dump`. This was verified end-to-end against
a real stack (see the commit on `docker-smoke-test` that documented it): a
dump taken by this system could not be restored using `postgres`'s own
`pg_restore` at all (`unsupported version ... in file header`), only by
routing the restore through the `backup` container's own newer client.
Fixed here by pinning `postgresql15-client` explicitly instead of the
floating `postgresql-client` meta-package, so both services always agree on
major version. **This is the kind of bug that only shows up the day someone
actually needs to restore** - worth remembering as an argument for
periodically testing restores for real, not just trusting that backups exist.

**Flat retention, unlike the non-Docker backup path (fixed on this branch).**
`qatrack/qatrack_core/management/commands/backup_site.py` - the backup
mechanism used by the Linux/Windows (non-Docker) deployment path - implements
a daily/weekly/monthly tiered retention scheme (`BACKUP_DAYS_TO_KEEP`,
`BACKUP_WEEKS_TO_KEEP`, `BACKUP_MONTHS_TO_KEEP`, defaulting to 7/5/12) so a
deployer keeps a longer history without keeping *every* daily backup
forever. The Docker `backup.sh` had none of that - a single flat window
applied to every backup, so a deployer could either keep a short history at
high resolution, or accept unbounded disk growth to keep a longer one, with
no middle ground. Ported the same three-tier scheme (daily/weekly/monthly,
same default values, configurable the same way - via environment variables
here rather than Django settings, since `backup.sh` runs outside Django
entirely) so the two backup paths behave consistently and a deployer moving
between them doesn't have to relearn different retention semantics.

Note that `backup_site.py` itself does not support PostgreSQL at all (its
own postgres branch is an explicit stub: *"PostgreSQL backup not natively
implemented in this script yet. Please use pg_dump."*) - so the Docker path's
separate, bespoke script isn't duplicated effort or an inconsistency to
"clean up" by unifying the two; it exists specifically to cover the engine
`backup_site.py` doesn't.

The one gap not fixed here
---------------------------

**Backups never leave the host.** `deploy/docker/backups` is a bind mount on
the same machine running the containers. If that host's disk fails, is
stolen, or is destroyed, the live database and every backup of it are lost
together - a single point of failure for both the primary copy and the
backup copy. This is the single biggest real risk in the current design, and
it's not something this branch fixes, because the right answer depends on
choices only a deployer/maintainer can make: what off-host storage is
available (another on-site machine, an S3-compatible bucket, a managed
backup service), what schedule, and whether backups need to be encrypted
in transit/at rest to satisfy the clinic's own data-handling requirements.
**Recommendation:** document a required post-install step (or a second,
optional `rclone`/`restic`/`rsync`-based sidecar service) that copies
`deploy/docker/backups` off the host on a schedule, and treat "backups exist
somewhere other than this one machine" as a release-blocking checklist item
for any real deployment, not an optional nice-to-have.

Alternatives considered and rejected (for now)
------------------------------------------------

**Continuous archiving / point-in-time recovery** (`pgBackRest`, `wal-g`,
`barman`, or Postgres's own WAL archiving). This is the technically stronger
answer - it reduces the recovery point objective from "up to 24 hours of
data since the last nightly dump" to "seconds," and is what's generally
recommended for a production database of real consequence. It was not
adopted as the *default* here: it adds a second long-running process, WAL
storage management, and meaningfully more operational complexity than a
clinic's IT staff should be expected to take on by default for what is
still a modest-scale application database. **Worth revisiting** as a
documented, opt-in "if you need stronger recovery guarantees than a nightly
dump" path for larger or more critical installations, rather than baking it
into the default `docker-compose` stack everyone gets.

**`pg_dumpall` instead of `pg_dump`.** `pg_dumpall` captures every database
plus cluster-wide objects (roles, tablespaces) in one dump; `pg_dump` only
captures the one database named. This stack only ever runs a single
application database (`qatrackplus`) with two roles created by the install
scripts (`qatrack`, `qatrack_reports`), so `pg_dump`'s narrower scope isn't
presently a real gap - but a full disaster-recovery drill should include
recreating those roles from the install docs/SQL scripts, not just assuming
`pg_dump`'s output alone reconstitutes a working instance.

**Docker volume/filesystem-level snapshots** (LVM, ZFS, or storage-driver
snapshots). Not adopted because it ties the backup strategy to a specific
host's storage technology, which this project has no control over or
visibility into across the range of environments it's deployed to. Could be
a reasonable *supplementary* layer for a deployer whose host already has
snapshotting infrastructure, but isn't portable enough to be the project's
own recommended mechanism.

**A managed database service** (e.g. a cloud provider's managed Postgres).
Out of scope - this deployment model is explicitly self-hosted
`docker-compose` on a single host; a managed service would be a different
deployment model entirely, not a change to this one.

Summary
-------

The current pg_dump-plus-cron approach is the right *category* of solution
for this project's actual deployment model and audience. Two real bugs in it
are fixed on this branch (the version mismatch that made restores silently
impossible, and the missing tiered retention). The one gap left open -
backups never leaving the host - is a real, significant risk, but the right
fix depends on deployment-specific infrastructure choices this evaluation
can't make on a deployer's behalf; it's recorded here as the clear next
priority rather than implemented speculatively.
