# Decisions to take before 4.0.2 is finalised

Not part of the published documentation — `docs/conf.py` builds `.rst`, so this file is
inert. It exists so that a decision nobody has taken yet is visible in the branch that
has to carry it, rather than remembered.

Delete this file when the decisions below are made and applied.

## 1. The `releases/4.0` sentence is false for Docker, and these pages repeat it

Six upgrade pages carry some form of:

> You never name a version. The installation guide checks out the ``releases/4.0``
> *branch* rather than a version tag, so the branch carries each patch as it is released
> and a ``git pull`` is all that moves you between them.

**It is true for Linux and Windows.** `linux.rst:118` and `win.rst:85` both run
`git checkout releases/4.0`, so a site installed from those guides really does follow
the 4.0 series and really can upgrade with `git pull`.

**It is false for Docker.** `docs/install/docker.rst` runs a bare `git clone` with no
branch argument, so the clone lands on the default branch — `master`, which at the time
of writing describes itself as `4.0.0-36-g5579e0dd`, not 4.0.1. A Docker site built by
the book is therefore **not on a release at all**, and its `git pull` follows `master`.
Measured by crane on 2026-10-23 while upgrading a real 4.0.1 Docker install.

This branch adds `docker_upgrade_from_4_0_1.rst`, `linux_upgrade_from_4_0_1.rst` and
`win_upgrade_from_4_0_1.rst`, and **each repeats the sentence**, so the claim is being
propagated rather than merely inherited.

### The choice

**Option 1 — correct the Docker pages.** Change the two Docker instances
(`docker_upgrade_from_4_0.rst:14`, `docker_upgrade_from_4_0_1.rst:15`) to say what
`docker.rst` actually does. Smallest change; leaves Docker sites tracking `master`.

**Option 2 — make `docker.rst` check out `releases/4.0`**, as Linux and Windows already
do. One line in the install guide, after which every instance of the sentence is true,
Docker sites track the 4.0 series, and `git pull` means what the upgrade pages say it
means.

**Option 2 is the better fix and the larger decision.** The sentence being wrong is a
documentation defect; a Docker site silently running the default branch instead of a
release is a deployment one, and it is the reason crane's clone came up as
`4.0.0-36-g5579e0dd`. It also changes what existing Docker sites should do, so it needs
a line in the upgrade notes telling them to check out the branch once — which is cheap,
and is the same shape as the `.env` step already documented here.

**Not decided.** Cody, 2026-10-26.

## 2. The upgrade page title, which is now probably fine

`docker_upgrade_from_4_0.rst` is titled *"Upgrading a Docker 4.0.0 installation to
4.0.1"*, and its body used to say the steps apply to any 4.0.x patch — so the title
under-described it.

**This branch resolves that by splitting the pages per upgrade path**, which makes the
existing title accurate: that page really is 4.0.0 → 4.0.1, and
`docker_upgrade_from_4_0_1.rst` is 4.0.1 → 4.0.2. A proposed change that generalised the
title has been dropped, because it would have fought the split.

**Worth re-reading once the split is final**, in case any page still claims to cover
more than its title says.

## 3. The intro claim about migrations is now true, and was not

`docs/release_notes.rst`'s 4.0.2 section says *"This release runs database migrations;
4.0.1 did not."* That was false while the migration PR sat closed — `develop` and
`v4.0.1` both carried 231 migration files. Under the 2026-10-26 release split the
migrations land, so the sentence is correct. **If the migrations slip out of 4.0.2, this
sentence and the new upgrade pages' "does run database migrations" have to come back
out.**
