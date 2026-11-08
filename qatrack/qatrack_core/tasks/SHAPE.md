# §4, as far as this branch takes it

**A demonstration, not a migration.** Branch `prep/868-s4-shape`, off q#868 at
`5ef660e8`. Nothing in `poe_tasks/` is changed yet, so q#868 is unaffected.

## What is here

| verb | why this one |
|---|---|
| `test-gui` | the task whose 25 echoed lines prompted this, and the one that lost `-- -k test_x` forwarding. `classify()` takes the mode and browser in either order, singly, or not at all |
| `cover` | shows what §3 could not do: `--skip-covered` is an ordinary argparse boolean, so `cover-mo` folds in and four coverage names become one |
| `ci-reminder` | the smallest body, and the noisiest in practice - `poe ci` is the pre-push command, and it ended by echoing six `print()` calls |

Measured already: the classifier accepts `headless firefox` and
`firefox headless` identically, `watch` alone, nothing at all, and answers a
typo by naming both vocabularies - which argparse cannot do for two positionals,
because it can only say that a browser is not a valid mode.

## What is not here

**No task is wired to it.** The three `cmd` lines are drafted in this file
below but not applied; a first attempt failed on an anchor and wrote nothing, so
`poe_tasks/` is untouched.

Thirteen bodies unported, 439 echoed lines in total: `test-integration` 79,
`dev-init` 56, `format-changed` 48, `test-engine` 31, `_engine-driver-check` 30,
`test-order` 29, `schema` 25, `generate-sample-data` 21,
`_engine-settings-from-template` 21, `check-migrations` 18, `_dev-clean` 12,
`test-databases-down` 11, `_compose-up` 11, `dump-data` 9, `make-schema` 7.

No tests yet. The point of §4 is that they import functions rather than
compiling strings out of TOML, so `test_poe_tasks.py` would gain real unit tests
for `classify()` and keep a few subprocess tests for the `.bak` guards.

## The three lines that would wire it up

```toml
# tests.toml
cmd = "python -m qatrack.qatrack_core.tasks test-gui ${mode} ${browser}"

# coverage.toml
cmd = "python -m qatrack.qatrack_core.tasks cover ${path} ${skip_covered}"

# ci.toml
cmd = "python -m qatrack.qatrack_core.tasks ci-reminder"
```

`${mode}` and `${browser}` vanish entirely when unset - measured, no empty token
and no dangling flag - which is what lets one line serve all five invocations.
