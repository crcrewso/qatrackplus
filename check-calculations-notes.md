# Checking calculation procedures — implementation notes

Notes on the `check_calculations` work: why it exists, the decisions worth
questioning during review, what the tests cover, and what deliberately waits
for 4.1. Written for whoever reviews or picks this up; the user-facing
documentation is in `docs/admin/qa/tests.rst`.

Branch: `feature/check-calculations`, based on `crcrewso/poethepoet-tasks`.

## Why

Calculation procedures are Python written by each clinic, and they run with
whatever NumPy, SciPy, pandas and pydicom QATrack+ ships. Raising the NumPy pin
to 2.x can therefore break a site's own tests, or quietly change their results,
without anything in QATrack+ changing. Until now the only way to find out was
to perform every test list by hand, so nobody would, and the first sign of
trouble would be a physicist at a linac.

This adds a check that can be run before the upgrade (to predict breakage) and
after it (to prove what actually broke).

## What was built

| Path | What it is |
|---|---|
| `qatrack/qa/calculation_check.py` | The engine: scan, planning, recalculation, comparison |
| `qatrack/qa/management/commands/check_calculations.py` | Command line front end (text/CSV/JSON, `--output`) |
| `qatrack/qa/views/admin.py` | `CheckCalculations` page and `CheckCalculationsRun` endpoint |
| `qatrack/qa/templates/admin/qa/test/` | The page, and the changelist button that links to it |
| `qatrack/admin_media/js/check_calculations.js` | Runs the recalculation jobs one at a time and fills in the table |
| `qatrack/qa/views/perform.py` | The only change to existing behaviour (see below) |
| `pyproject.toml`, `Makefile` | `poe check-calculations` and `make check-calculations` |

## How it works

Two independent checks, because neither is sufficient alone.

**The scan** parses each procedure and resolves references to NumPy through
whatever name it was imported under (`import numpy as np`, `from numpy import
NaN`, `from numpy import *`, or the `numpy` the calculation context provides
without an import). Names are matched against a table of what NumPy 2 removed,
built from NumPy's own `_expired_attrs_2_0.py` plus a diff of what exists in
1.26 and not in 2.5.3, so the advice matches NumPy's own wording. Anything not
in the table is resolved against the *installed* NumPy, which catches removals
the table doesn't know about and reports deprecation warnings raised on
attribute access. There are also three call-shape rules: `np.array(...,
copy=False)`, `np.linalg.lstsq` without `rcond`, and `.ptp()`/`.itemset()`/
`.newbyteorder()` called on something that might be an array.

The scan needs no data, so it works before upgrading. That is the whole point
of having it as well as the recalculation.

**The recalculation** takes the most recent saved result of each test on each
unit and calculates it again through the *production* `CompositePerformer` and
`UploadHandler` — not a reimplementation — with the data rebuilt exactly as
`qa/static/qa/js/qa.js` posts it when a test list instance is opened for
editing. Getting that payload right matters more than it sounds:

- The browser sends numbers through `JSON.stringify`, so a saved `2.0` arrives
  at a procedure as `2`, not `2.0`. Any procedure that puts a value in a string
  would otherwise show a false "Changed".
- Dates and datetimes are formatted with the same input format the views parse
  back, so the round trip matches the page, minute precision included.
- Upload tests contribute their *saved* analysis result to dependent
  composites, so a broken upload doesn't cascade into its dependants and hide
  the root cause.

Results are compared with what was saved. Numbers use `math.isclose` with
`rtol=1e-9`, `atol=1e-12` (configurable), which ignores last-bit noise from a
new NumPy's summation order but still catches float32 promotion differences
around 1e-7. String composites are compared as JSON where possible, since the
page saves non-string results with `JSON.stringify` and the API saves them with
`str()`.

While procedures run, deprecation and future warnings raised by *their own*
code are captured and reported. This is what catches pandas 3 changes, which no
NumPy-focused scanner could see — a `fillna(method="ffill")` shows up as a
warning under pandas 2 and as a broken test under pandas 3.

### Read-only

- Every job runs in a transaction that is always rolled back.
- `UTILS.write_file` still converts the object (so a conversion that breaks is
  caught) but stores nothing.
- Verified, not assumed: a demo database was byte-identical after repeated runs
  from both the command line and the admin page. Only Django's cache table
  changed, from ordinary page rendering.

Procedures still run exactly as they do during QC, so side effects *outside*
the database — writing to a network share, say — happen again. That is
documented rather than prevented, since preventing it would mean not running
the real code.

### The one change to existing behaviour

`CompositeUtils` gained `exclude_test_list_instance_id`, defaulting to `None`,
applied in the three history lookups (`previous_test_list_instance`,
`previous_test_instance`, `get_test_instance`). Without it, recalculating a
saved instance can find *itself* as its own "previous" result: the lookups
filter on `work_completed` rounded up to the next minute, and API submissions
typically have `work_started == work_completed`. Procedures that compute drift
from a previous reading would then report a false "Changed".

The default preserves current behaviour exactly, so the Perform QC page is
unaffected. It is the one thing in this change that touches the QC calculation
path and deserves a careful read.

### Why the admin page posts one job at a time

An upload test doing a pylinac analysis can take seconds, and a site can have
many of them. Checking everything in one request would risk a proxy timeout, so
the page plans the work server-side and the JavaScript posts one job per
request, updating rows as results arrive. It also means progress is visible and
a long run can be left alone.

### Warning attribution, and a NumPy quirk worth knowing

Warnings are captured with a `showwarning` hook rather than by reading
`warnings.catch_warnings(record=True)` entries, because NumPy 1.25/1.26 emits
its `np.product` deprecation from a dispatcher with `stacklevel=3`, written for
a Python-level dispatcher that is now implemented in C. The warning therefore
lands on the `exec` line in `views/perform.py`, one frame past the procedure.
The hook walks the live stack to find the procedure's frame instead, and
ignores warnings that point inside a library, which are that library's
business. Procedures are compiled with the filename `__QAT+COMP_<macro name>`,
which is what makes the attribution possible at all.

`warnings.catch_warnings` swaps process-global state, so the capture is
serialised with a module-level lock; two admins checking at once on a threaded
server would otherwise leave warnings swallowed process-wide.

### Sample files for upload tests

An upload test that has never been performed has no file to recalculate from.
Rather than add a model field (and a migration, which does not belong in a
patch release), the check runs any file attached to the test whose label starts
with `check_calculations`. The admin already supports attaching files to a
test, so this needs no UI work. The trade-off: such files are also listed with
the test's procedure when QC is performed, which is documented.

## What it deliberately does not do

- Only the most recent result per unit is recalculated, so a branch that only
  runs for unusual values may go untested. The scan covers unexecuted code, so
  the two checks complement each other.
- No static rules for pandas; its breakage surfaces through runtime warnings
  and recalculation instead.
- A procedure that loops forever hangs the check, exactly as it would hang the
  Perform QC page.

## Tests

`qatrack/qa/tests/test_calculation_check.py`, 72 tests. They pass under NumPy
1.26.4/pandas 2.3.3 and under NumPy 2.5.3/pandas 3.0.5; the version-dependent
expectations are derived from `cc.NUMPY_MAJOR` so the suite is honest under
both.

### `TestScanProcedure` (17) — reading a procedure's source

| Test | Purpose |
|---|---|
| `test_clean_procedure` | A procedure using only supported NumPy reports nothing |
| `test_empty_procedure` | Empty and `None` procedures are not errors |
| `test_syntax_error` | Invalid Python is reported as broken, with its line |
| `test_numpy_from_calculation_context` | `numpy` is found without an import, as the context provides it |
| `test_numpy_alias` | `import numpy as np` is followed, and the line number is right |
| `test_from_numpy_import` | `from numpy import NaN` is reported at the import |
| `test_star_import` | `from numpy import *` finds bare removed names |
| `test_submodule_alias` | `import numpy.linalg as la` resolves through the alias |
| `test_removed_module_reported_once` | A removed module is reported at its import, not on every use |
| `test_reassigned_alias_is_not_numpy` | A name reassigned to something else is no longer treated as NumPy |
| `test_numpy_core` | `numpy.core` is reported as a deprecated alias, not a removal |
| `test_not_in_installed_numpy` | A name missing from the installed NumPy is an error naming the version |
| `test_array_copy_false` | `np.array(..., copy=False)` is flagged; `copy=True` is not |
| `test_lstsq_rcond` | `lstsq` without `rcond` is flagged; passing it either way is not |
| `test_removed_array_methods` | `values.ptp()` is flagged, `np.ptp(values)` is not |
| `test_dtype_newbyteorder_still_exists` | `x.dtype.newbyteorder()` is not a false positive |
| `test_crlf_line_numbers` | Line numbers are right for procedures saved with CRLF |

### `TestRecalculation` (24) — composites, defaults, and the guarantees

| Test | Purpose |
|---|---|
| `test_unchanged` | A result that still matches reports OK with both values |
| `test_changed` | An edited procedure reports Changed with the relative difference |
| `test_within_tolerance` | Floating point noise is ignored; zero tolerance catches it |
| `test_broken` | A failing procedure reports the error line and keeps the traceback as detail |
| `test_only_latest_result_per_unit` | Older results are not recalculated |
| `test_skipped_results_are_passed_over` | A skipped latest result falls back to the last real one |
| `test_every_unit` | Each unit is checked, and `units=` narrows it |
| `test_no_saved_results` | A never-performed test is "Not recalculated", not OK |
| `test_scan_only` | Scanning without recalculating reports the scan's status |
| `test_input_missing` | A test added to the list later is reported as a missing input, by name |
| `test_whole_numbers_arrive_as_integers` | The JSON number emulation: saved `2.0` reaches a procedure as `2` |
| `test_string_composite_saved_as_json` | JSON saved by the page compares equal despite formatting |
| `test_string_composite_repr_change` | NumPy 2's scalar `repr` inside a string is caught as Changed |
| `test_dates` | Date and datetime values survive the format round trip |
| `test_meta` | META carries the unit number, test list name and work dates |
| `test_not_its_own_previous_result` | A saved instance is excluded from its own history lookups |
| `test_nothing_is_saved` | Database writes by a procedure are rolled back and no attachment is created |
| `test_write_file_conversion_still_checked` | `UTILS.write_file` still converts, so a broken conversion is caught |
| `test_default_value_procedure` | Default-value procedures run, and a broken one is reported |
| `test_removed_from_test_list` | A test no longer in the list says so rather than erroring |
| `test_deprecation_warnings` | A warning from the procedure's own code is reported and raises the status |
| `test_deprecation_warning_pointing_past_the_procedure` | The NumPy `stacklevel` case is still attributed to the procedure |
| `test_warnings_pointing_elsewhere_are_ignored` | A library's internal warning is not blamed on the procedure |
| `test_test_list_crash` | A procedure that cannot be tokenised fails the list without hiding the cause |

### `TestUploadRecalculation` (10) — file upload tests

| Test | Purpose |
|---|---|
| `test_unchanged` | An upload recalculated from its saved file matches |
| `test_changed` | A different analysis result is reported as Changed |
| `test_broken` | A failing upload procedure is reported as broken |
| `test_deprecation_warnings` | Warnings from an upload procedure are attributed to it |
| `test_file_missing` | A deleted upload file is "Not recalculated", not an error |
| `test_upload_results_used_by_composites` | Composites see the saved upload result |
| `test_sample_file` | A `check_calculations`-labelled attachment is run |
| `test_other_test_attachments_are_not_samples` | Ordinary attachments (procedure documents) are not run |
| `test_sample_file_broken` | A sample file that fails reports broken |
| `test_sample_file_test_not_assigned` | A test on no unit says so rather than failing |

### `TestJob` (2), `TestStatus` (1) — the small pieces

| Test | Purpose |
|---|---|
| `test_round_trip` | A job survives being posted to the server as JSON |
| `test_invalid` | Malformed jobs are rejected (bad kind, no tests, missing ids) |
| `test_status` | A test's status is the worst of its checks, and one unit recalculating is enough |

### `TestCommand` (7), `TestCommandOutputFile` (4) — the command line

| Test | Purpose |
|---|---|
| `test_all_ok` | A clean run summarises and exits 0 |
| `test_broken` | A broken test is named, with its error, and exits 1 |
| `test_changed` | A changed result shows both values; `--strict` makes it exit 1 |
| `test_scan_only` | `--scan-only` doesn't recalculate |
| `test_filters` | `--test`, `--type`, `--test-list` select; unknown names and units error |
| `test_json` | JSON output carries versions, statuses and saved values |
| `test_csv` | CSV output has a header and one row per test |
| `test_saves_report` | `--output` writes the report and prints only path and summary |
| `test_saves_csv` | `--output` works with `--format csv` |
| `test_no_colour_codes_in_report` | A saved report has no terminal escape codes, even with `--force-color` |
| `test_unwritable_report` | An unwritable path fails with a clear `CommandError` |

### `TestAdminPage` (7) — the admin page

| Test | Purpose |
|---|---|
| `test_linked_from_test_list` | The Tests changelist links to the page |
| `test_scan_shown` | Scan findings are rendered with the test's row |
| `test_jobs_planned` | The page plans the jobs its JavaScript will post |
| `test_run` | The endpoint recalculates one job and returns saved/recalculated values |
| `test_run_invalid_job` | Malformed posts return 400 rather than 500 |
| `test_run_missing_instance` | A stale job returns an error result, not an exception |
| `test_permission_required` | Both views need `qa.change_test` |

## Verification beyond the suite

- The full suite on this branch: 1278 passed, 55 skipped, 0 failed.
- The same change with NumPy 2.5.3 and pandas 3.0.5 (a scratch worktree with
  the #854 compatibility commit cherry-picked): all 72 new tests pass, and the
  full suite passed there too on the develop-based version of this work.
- A demo database was built through the real `CompositePerformer`/`UploadHandler`
  under NumPy 1.26, then checked under both versions. `np.product`, `.ptp()`
  and `fillna(method=)` went from Warning to Broken, and a string composite went
  from OK to Changed because of NumPy 2's scalar `repr` — which is the case that
  justifies having the recalculation at all.
- The admin page was driven in a browser under both versions: scan on load,
  recalculation with progress, the problems-only filter, and tracebacks behind
  a details toggle.

## For 4.1, or later — not 4.0.1

1. **Translation catalogues.** Every new string is already wrapped in
   `gettext`/`{% trans %}`, but the `fr`, `fr-ca` and `es` catalogues have no
   entries for them. Regenerating and translating is 4.1 work; nothing in this
   change needs to move for it to happen.
2. **The NumPy 2 / pandas 3 bump itself (#854).** A dependency change is not a
   patch-release item. This check is meant to ship *first*, so that sites can
   scan before the pins move. The bump also needs the two QATrack+ uses that
   NumPy 2 removed: `np.float_` in `qatrack/qatrack_core/serializers.py` and
   `np.NaN` in `qatrack/qa/control_chart/leastsquaresfit.py`.
3. **The work list.** The check page should become something an admin can work
   through: each problematic test opening in its own window, and the list
   tracking what has been dealt with. Today each test links to its admin page in
   a new tab and the table can be filtered to problems. Noted in the
   `CheckCalculations` docstring.
4. **A first-class sample file for upload tests.** The `check_calculations`
   label convention exists to avoid a migration. A real field, or a flag on the
   attachment inline, would be clearer and would stop sample files appearing in
   the procedure notes when QC is performed — but it needs a migration.
5. **Static rules for pandas.** Worth adding alongside the pandas 3 bump:
   `fillna(method=)`, `applymap`, chained assignment under copy-on-write, and
   the removed frequency aliases. Runtime warnings catch these today, but only
   on code paths that actually run.
6. **A release checklist step.** `RELEASE_CHECKLIST.md` lives on the
   settings-audit stack, not this branch, so it can't be updated here without
   cascading. Once the branches converge, running `check_calculations` belongs
   in the release checklist and in the upgrade runbooks.
7. **Scheduled checking.** QATrack+ already runs django-q2. A scheduled check
   with a notification would catch breakage after an unattended library update,
   rather than waiting for somebody to run it.
8. **Deeper coverage options.** Recalculating more than the latest result per
   unit (`--history N`), covering every test list a test belongs to rather than
   the latest instance per unit, and an option to feed *new* upload results into
   dependent composites instead of the saved ones. All are behaviour and runtime
   trade-offs that want a minor release.
9. **Windows verification.** `poe check-calculations` is a `cmd` task and needs
   no shell, but like the rest of the poe tasks it has only been run on Linux.
   It should be included when those are exercised on a real Windows host.
