# Issue #713 Detailed Analysis (Special Character Filtering)

Date: 2026-04-20

## Ticket Comment Posted
A short summary-table comment was posted to upstream GitHub issue #713 in `qatrackplus/qatrackplus`.

## Detailed Findings
Filtering with non-ASCII values (example: `Hôpital X`) fails due to encoding mismatches and unstable filter keys in the listable pipeline.

### Source 1: Deprecated JS escaping in option values
- Layer: Browser option rendering
- File: `.venv/Lib/site-packages/listable/static/listable/js/jquery.dataTables.columnFilter.js`
- Evidence:
  - `value="' + escape(aData[j]) + '"`
  - `value="' + escape(aData[j].value) + '"`
- Why it breaks:
  - `escape()` is deprecated and can emit `%uXXXX`-style sequences that diverge from standard URI encoding behavior.
- Recommended direction:
  - Use `encodeURIComponent()` for outbound values and matching decode logic server-side.

### Source 2: Deprecated JS escaping in live-filter reconciliation
- Layer: Browser filter sync
- File: `.venv/Lib/site-packages/listable/static/listable/js/listable.js`
- Evidence:
  - `filters.map((option) => escape(option))`
- Why it breaks:
  - Re-encoding available options with `escape()` can produce values that do not match already-rendered option values consistently.
- Recommended direction:
  - Align with `encodeURIComponent()` and ensure one canonical encoding strategy.

### Source 3: String-based filter values generated in template tag path
- Layer: Python filter serialization
- File: `.venv/Lib/site-packages/listable/templatetags/listable.py`
- Evidence:
  - `values_to_dt()` creates `{"value": str(escape(x[0])), "label": escape(str(x[1]))}`
- Why it breaks:
  - Human-readable strings are used as filter keys, increasing sensitivity to encoding, collation, and normalization differences.
- Recommended direction:
  - Use stable IDs (PKs) as filter values, display labels only for UI text.

### Source 4: Server decode chain is tightly coupled to client escaping style
- Layer: Server request decoding
- File: `.venv/Lib/site-packages/listable/views.py`
- Evidence:
  - `utils.unquote_unicode(...).split('`|`')` combined with `unescape(...)`
- Why it breaks:
  - Decoding behavior depends on how the browser encoded values; mixed/legacy encodings increase mismatch risk.
- Recommended direction:
  - Normalize client encoding to URI encoding and simplify server decoding to standard UTF-8 URL decode.

### Source 5: Filter keys derive from display fields
- Layer: Query/filter key design
- File: `.venv/Lib/site-packages/listable/views.py`
- Evidence:
  - `values_list(field, field)`
- Why it breaks:
  - Using display text as both key and label causes fragile equality matching across encoding boundaries.
- Recommended direction:
  - Build filter tuples as `(pk, display_label)` and filter on `...__id__in` where possible.

## Summary Table

| # | Layer | File | Mechanism | Proposed fix |
|---|---|---|---|---|
| 1 | JS option rendering | `.venv/Lib/site-packages/listable/static/listable/js/jquery.dataTables.columnFilter.js` | Uses deprecated `escape()` for option values | Use `encodeURIComponent()` |
| 2 | JS live-filter matching | `.venv/Lib/site-packages/listable/static/listable/js/listable.js` | Re-encodes with `escape()` before matching option values | Use `encodeURIComponent()` consistently |
| 3 | Python value prep | `.venv/Lib/site-packages/listable/templatetags/listable.py` | `values_to_dt()` uses escaped display strings as filter values | Use stable IDs (PKs) as option values |
| 4 | Python decode path | `.venv/Lib/site-packages/listable/views.py` | Decode chain must align with browser encoding behavior | Simplify to standard URL decoding once JS is normalized |
| 5 | Filter key design | `.venv/Lib/site-packages/listable/views.py` | `values_list(field, field)` uses localized strings as keys | Build filters as `(pk, display_label)` |

## Implementation Priority
1. Replace all remaining `escape()` usage in listable JS paths with `encodeURIComponent()`.
2. Move SELECT_MULTI filters to ID-based values (PKs) and label-only display strings.
3. Simplify server decode path once client encoding is standardized.
4. Add regression tests with accented and non-Latin characters.
