# Assistant Response Archive

This file stores assistant replies per user request.

## Conventions
- Document all future assistant interactions in the `.ai/` folder.
- For all assistant-authored posts/comments, prepend the body with: `Generated with AI`

## 2026-04-20 - Issue #713 follow-up
- Posted a short summary-table comment to upstream GitHub issue #713 (`qatrackplus/qatrackplus`).
- Saved full detailed analysis to `.ai/github/issue_713_detailed_analysis.md`.
- Set preference to continue saving future answers into `.ai/`.

## 2026-04-20 - Preference update
- Confirmed and enabled persistent preference to document all assistant interactions under `.ai/`.
- Confirmed and enabled persistent preference that all assistant-authored posts/comments begin with `Generated with AI`.
- Updated `.ai/chat/assistant_responses.md` conventions section to reflect both rules.

## 2026-04-20 - Dev branch Django convention review
- Reviewed Dev branch and identified top 10 high-impact, functioning but non-conventional Django patterns.
- Saved ranked findings and a prioritized remediation roadmap to `.ai/reviews/dev_branch_django_convention_top10_plan.md`.

## 2026-04-20 - Concrete backlog requested
- Created an execution-ready backlog with epics, ticket-ready tasks, acceptance criteria, dependencies, and a 16-PR sequence.
- Saved backlog to `.ai/reviews/dev_branch_django_convention_concrete_backlog.md`.

## 2026-04-20 - Project 6 draft sync
- Refreshed GitHub CLI auth scopes for project access (`read:project`, `project`) using device flow.
- Added the concrete backlog drafts directly to Project 6.
- Verified Project 6 now has one PR-prefixed draft for each item PR-01 through PR-16.
- Saved sync record to `.ai/github/project6_backlog_drafts_added.md`.

## 2026-04-20 - Documentation audit
- Scanned all docs/ files against current codebase, pyproject.toml, and deploy/ configs.
- Identified 22 issues: 6 High, 10 Medium, 6 Low.
- Key findings: all install guides target v3.1.1.4 (not v4.0.0), deprecated sql_server.pyodbc engine throughout, no upgrade path doc v3→v4, schema.rst shows v0.3.0 diagram, BitBucket links, CherryPy references post Apache adoption.
- Saved full audit to `.ai/reviews/documentation_audit.md`.

## 2026-04-20 - Additional security and CI issues added to Project 6
- Identified 4 untracked issues: hard-coded SECRET_KEY (P0), open API permission_classes (P0), no GitHub Actions CI (P1), plaintext credentials in local_settings.py (P1).
- Added as drafts SEC-01, SEC-02, CI-01, SEC-03 to GitHub Project 6.

## 2026-04-20 - schema.rst fix (audit high severity #6)
- Updated `docs/developer/schema.rst`:
  - Title changed from "QATrack+ v0.3.0 Database Schema" to "QATrack+ Database Schema"
  - Figure now references `qatrack_schema_3.1.0.svg` (the current SVG already present in images/)
  - Ubuntu instructions updated: `python-dev` → `python3-dev`, 18.04 → 22.04, `uv pip install` → `uv sync --group dev`
  - Replaced BitBucket "older versions" link with GitHub URL

## 2026-04-20 - Option A skin configurability on dedicated branch
- Created branch `feature/site-skin-setting-option-a`.
- Implemented setting-driven AdminLTE skin selection:
  - Added `AVAILABLE_ADMINLTE_SKINS` and `SITE_SKIN` defaults in `qatrack/settings.py`.
  - Exposed `SITE_SKIN` via `qatrack.context_processors.site` with fallback to `skin-black-dark`.
  - Updated `qatrack/templates/site_base.html` to use `SITE_SKIN` for both skin stylesheet link and body class.

## 2026-04-20 - Install guide for skin setting and palette visuals
- Added `docs/install/site_palette.rst` with admin-facing steps to set `SITE_SKIN` in `local_settings.py`.
- Documented available skin values and apply/restart steps.
- Added three palette preview images:
  - `docs/install/images/palette_default_black_dark.svg`
  - `docs/install/images/palette_green.svg`
  - `docs/install/images/palette_grayscale.svg`
- Linked the new page in `docs/install/install.rst` under "Configuring your QATrack+ Instance".

## 2026-04-20 - Added recommended settings and screenshots to docs
- Updated `docs/install/site_palette.rst` with explicit setting snippets for:
  - default (`SITE_SKIN = "skin-black-dark"`)
  - recommended inviting option (`SITE_SKIN = "skin-green-light"`)
  - neutral grayscale (`SITE_SKIN = "skin-black-light"`)
- Updated labels/captions so screenshot docs align with the recommended green-light setting.
- Added a `Site Color Skin Setting` section to `docs/install/config.rst` linking to the full guide.

## 2026-04-20 - Palette feature commit, GitHub comment, and branch switch
- Committed staged palette implementation and docs as commit `f9637d5f428610d0a3c5e4c4abad682bb916ca97` on branch `feature/site-skin-setting-option-a`.
- Pushed branch to origin.
- Added GitHub commit comment summarizing implementation and recommended default (`skin-green-light`).
- Switched working branch back to `Dev`.

## 2026-04-20 - Local Site Code custom functions feature draft
- Created branch `feature/local-site-code-custom-functions`.
- Added Local Site Code extensibility support:
  - New setting `LOCAL_SITE_CODE_FUNCTION_MODULES` in `qatrack/settings.py`.
  - New loader `qatrack/qa/local_site_code.py` with validation and duplicate detection.
  - Wired loader context into all composite/upload calculation contexts in `qatrack/qa/views/perform.py`.
- Added sample module `local_site_code_sample.py` with two functions:
  - `is_prime(value)`
  - `factorial(value)`
- Added docs:
  - `docs/install/local_site_code_custom_functions.rst`
  - Updated `docs/install/config.rst`
  - Updated `docs/install/install.rst` to include new doc in toctree.
- Added tests in `qatrack/qa/tests/test_local_site_code.py`.

## 2026-04-20 - Local Site Code commit and GitHub comment
- Committed staged Local Site Code implementation as `261831cdf72a4f71180fb07881c8a2b4a10e550a`.
- Pushed branch `feature/local-site-code-custom-functions` to origin.
- Added GitHub commit comment summarizing changes and noting tests were not executed per request.

## 2026-04-20 - Test suite omissions and structure audit
- Switched back to `Dev` branch for analysis.
- Identified top omissions:
  - Missing anonymous/unauthorized API tests for composite and upload endpoints while `permission_classes = []`.
  - No tests found for `issue_tracker` app views/models/forms.
  - No tests found for `middleware` package behavior (login-required, maintain_filters, profiler).
- Identified structural issues:
  - Very large monolithic test modules (for example `qa/tests/test_views.py`, `qa/tests/test_models.py`, `api/qa/tests/test_api.py`).
  - Inconsistent test layout and naming (`tests.py`, `tests/tests.py`, distributed test files outside app-level `tests/` package).
  - Presence of skipped flaky tests (`@pytest.mark.skip` citing sqlite segfault) reduces confidence in critical paths.

## 2026-04-20 - Test-suite remediation plan with factory-pattern guidance
- Created execution plan at `.ai/reviews/test_suite_remediation_plan.md`.
- Included top 3 omissions, structural issues, phased delivery, first 5 PR slices, and explicit Yes/No comments on where to replace tests with factory pattern.

## 2026-04-20 - Test-suite refactor branch and prepared commit
- Created branch `feature/test-suite-local-site-code-remediation`.
- Refactored API permission tests into dedicated file with renamed test names and inline comments indicating previous names.
- Added baseline test modules for issue tracker app and middleware package in standardized `app/tests/test_*.py` layout.
- Kept changes focused and prepared commit without executing the updated test suite.
