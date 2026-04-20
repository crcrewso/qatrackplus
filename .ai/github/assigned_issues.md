# GitHub Issues Assigned to @crcrewso
_Fetched: April 20, 2026_

## qatrackplus/qatrackplus

| # | Title | Summary |
|---|-------|---------|
| [#713](https://github.com/qatrackplus/qatrackplus/issues/713) | Filtering fails on special characters | Filter dropdowns break on accented/non-ASCII site/unit names (e.g. "Hôpital X"). Likely a character encoding mismatch — filter uses label text as value rather than a DB ID. |
| [#712](https://github.com/qatrackplus/qatrackplus/issues/712) | Request: expand test text boxes | Community request to enlarge the test description/script text areas in the admin for better legibility. Touches `test_admin.js` and `admin_description_editor.js`. |
| [#711](https://github.com/qatrackplus/qatrackplus/issues/711) | Windows migration to Apache from CherryPy | Migrate Windows deployment from CherryPy/IIS to Apache (aligns with Linux, is Django-recommended). **Resolved by `deploy/apache/apache24_windows.conf` created April 20, 2026.** |
| [#707](https://github.com/qatrackplus/qatrackplus/issues/707) | Manually rerun all composite tests in a test list | Feature request to add a UI action to recalculate all composite tests at once, e.g. by clicking the "calculating/calculated" icon. |
| [#703](https://github.com/qatrackplus/qatrackplus/issues/703) | Review all current branches | Housekeeping — too many stale branches from outdated explorations need to be pruned. |
| [#689](https://github.com/qatrackplus/qatrackplus/issues/689) | Pytest parameterization | Test suite quality — reduce the number of asserts-per-test using pytest fixtures and parameterization. |
| [#680](https://github.com/qatrackplus/qatrackplus/issues/680) | Initial boolean value not showing correctly | Setting a boolean test's initial value to `False` displays `True` in the UI until manually toggled. Reported against v3.1.1.2. |
| [#677](https://github.com/qatrackplus/qatrackplus/issues/677) | Bug with Chinese characters in Fault types | Clicking "All Fault Types" fails when a fault type name contains Chinese/multi-byte characters. Likely same root cause as #713. |
| [#513](https://github.com/qatrackplus/qatrackplus/issues/513) | Add charts to reports | Feature request (migrated from Bitbucket) — add simple trend charts to Test Instance Details PDF reports. |
| [#508](https://github.com/qatrackplus/qatrackplus/issues/508) | Compliance Report | Feature request — a report identifying missing QC instances for a given frequency/assigned test list (e.g. daily tests not performed on certain days). |

## Other repos

| Repo | # | Title | Summary |
|------|---|-------|---------|
| crcrewso/DicomStrictCompare | [#41](https://github.com/crcrewso/DicomStrictCompare/issues/41) | DTA Settings | Add reference name per DTA setting; fix Annual QA settings footer. |
| crcrewso/DicomStrictCompare | [#28](https://github.com/crcrewso/DicomStrictCompare/issues/28) | Project name | Rename repo to "DCM Batch Compare", namespace to `DcmBatComp`. |
| crcrewso/DicomStrictCompare | [#23](https://github.com/crcrewso/DicomStrictCompare/issues/23) | Optional match parameters | Allow matching by UUID, plan name, field parameters, or a combination. |
| crcrewso/DicomStrictCompare | [#21](https://github.com/crcrewso/DicomStrictCompare/issues/21) | Add a gamma calculation | Add proper gamma algorithm instead of current DTA-only approach. |
| crcrewso/DicomStrictCompare | [#17](https://github.com/crcrewso/DicomStrictCompare/issues/17) | Gamma on CAX PDD | Export gamma value per comparison to Excel, including plan name. |
| crcrewso/DicomStrictCompare | [#14](https://github.com/crcrewso/DicomStrictCompare/issues/14) | Modification of algorithm | Match dose files by jaw parameters, not just names. |
| crcrewso/DicomStrictCompare | [#13](https://github.com/crcrewso/DicomStrictCompare/issues/13) | Add profiles to plots | Create profile plots at user-specified depths in addition to PDDs. |
| mlamey/BeamDeliveryTime | [#2](https://github.com/mlamey/BeamDeliveryTime/issues/2) | Plan sums | Show useful error message (not raw exception) when a plan sum is open. |
| pymedphys/pymedphys | [#1653](https://github.com/pymedphys/pymedphys/issues/1653) | Inconsistent Rows/Cols in Pinnacle extraction | Potential row/col definition mismatch in `image.py` and `rtdose.py`. |
| pymedphys/pymedphys | [#1635](https://github.com/pymedphys/pymedphys/issues/1635) | Pinnacle export 'all' option | Support `-p all` / `-t all` in the Pinnacle export CLI (mirrors `-i all` for images). |
| pymedphys/pymedphys | [#1597](https://github.com/pymedphys/pymedphys/issues/1597) | CT Iso ignored in Pinnacle conversion | CT center value in the ROI file is not applied, causing structure set offset errors. |
| pymedphys/pymedphys | [#1561](https://github.com/pymedphys/pymedphys/issues/1561) | ParseError: POI Color (Pinnacle) | Parser fails on colour value `"greyscale"` — needs a fallback/mapping for unknown colour names. |
| pymedphys/pymedphys | [#1555](https://github.com/pymedphys/pymedphys/issues/1555) | ParseError of plan.trial with Pinnacle module | YAML parser fails on `Store = { At .Pm = StringKeyDict { ... } }` blocks in older Pinnacle plans. |

---

## Notes

- **#711 and #677/#713** are directly connected to session work on April 20, 2026:
  - #711 is resolved by `deploy/apache/apache24_windows.conf`.
  - #677 and #713 share a root cause (non-ASCII text used as filter values instead of IDs) and should be tracked together.
