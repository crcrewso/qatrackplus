# Test Suite Remediation Plan (Dev Branch)

Generated with AI
Date: 2026-04-20

## Objectives

1. Close the three highest-risk testing omissions.
2. Reduce structural fragility in the test suite.
3. Standardize where factory-pattern setup should and should not be used.

## Top 3 Omissions and Remediation

### Omission 1: Missing anonymous/unauthorized coverage for open API calculation endpoints

- Code evidence:
  - qatrack/api/qa/views.py sets permission_classes = [] for CompositeCalculation and Upload.
  - qatrack/api/qa/tests/test_api.py primarily uses logged-in setup in setUp.

- Why high impact:
  - Security and access-control regression risk on endpoints that execute calculation flows.

- Remediation tasks:
  1. Add explicit unauthenticated access tests for composite and upload endpoints.
  2. Add explicit authenticated-but-insufficient-permission tests.
  3. Add expected status assertions (401/403 if secured, or explicit allow assertion if intentionally open).
  4. Add comments in tests documenting the intended policy.

- Suggested target files:
  - qatrack/api/qa/tests/test_api.py
  - (optional split) qatrack/api/qa/tests/test_api_permissions.py

- Factory-pattern replacement comment:
  - Replace with factory pattern: No (for the permission checks themselves).
  - Reason: Endpoint access checks should use minimal setup; factories here add indirection without much benefit.

---

### Omission 2: No issue_tracker app test coverage

- Code evidence:
  - qatrack/issue_tracker/views.py, models.py, forms.py exist.
  - No test modules found under qatrack/issue_tracker.

- Why high impact:
  - Full feature area has no regression protection (create/list/detail behavior, filters, model rules).

- Remediation tasks:
  1. Add issue tracker model tests (status defaults, priority/tag behavior).
  2. Add form tests (required fields, validation, tag binding).
  3. Add view tests for create/list/detail and filtering behavior.
  4. Add permission/auth tests for login-required behavior.

- Suggested target files:
  - qatrack/issue_tracker/tests/test_models.py
  - qatrack/issue_tracker/tests/test_forms.py
  - qatrack/issue_tracker/tests/test_views.py

- Factory-pattern replacement comment:
  - Replace with factory pattern: Yes.
  - Reason: Issue tracker setup is relational (status/priority/tag/user) and repeated object construction will become noisy quickly.

---

### Omission 3: No middleware test coverage

- Code evidence:
  - qatrack/middleware/login_required.py
  - qatrack/middleware/maintain_filters.py
  - qatrack/middleware/profiler.py
  - No middleware test modules found.

- Why high impact:
  - Middleware affects all requests and can cause site-wide behavior regressions.

- Remediation tasks:
  1. Add request/response flow tests for LoginRequiredMiddleware exempt URL logic and redirect behavior.
  2. Add tests for maintain_filters session interactions.
  3. Add tests for profiler middleware enable/disable behavior.
  4. Add edge-case tests for malformed paths and query strings.

- Suggested target files:
  - qatrack/middleware/tests/test_login_required.py
  - qatrack/middleware/tests/test_maintain_filters.py
  - qatrack/middleware/tests/test_profiler.py

- Factory-pattern replacement comment:
  - Replace with factory pattern: No (mostly).
  - Reason: Middleware tests should rely on RequestFactory and simple users; data factories are usually unnecessary except optional user fixtures.

## Structural Problems and Remediation

### Structural Problem A: Monolithic test modules

- Evidence examples:
  - qatrack/qa/tests/test_views.py
  - qatrack/qa/tests/test_models.py
  - qatrack/api/qa/tests/test_api.py

- Remediation tasks:
  1. Split each monolith by domain behavior (for example, composite, upload, autosave, review).
  2. Keep file size under a practical threshold (for example <= 400 lines target).
  3. Introduce per-module helper fixtures/factories.

- Factory-pattern replacement comment:
  - Replace with factory pattern: Yes (selectively).
  - Reason: Large modules often duplicate model setup; factories reduce duplication and improve readability.

---

### Structural Problem B: Inconsistent test layout and naming

- Evidence examples:
  - qatrack/units/tests.py versus app/tests/test_*.py pattern.
  - qatrack/faults/tests/tests.py naming inconsistency.

- Remediation tasks:
  1. Standardize to app/tests/test_*.py structure.
  2. Move tests.py modules into tests/ packages where practical.
  3. Add a short CONTRIBUTING test layout section.

- Factory-pattern replacement comment:
  - Replace with factory pattern: Mixed.
  - Reason: This is mainly organization; apply factories where repeated object setup exists, not as a blanket rule.

---

### Structural Problem C: Skipped/flaky critical-path tests

- Evidence example:
  - qatrack/api/qa/tests/test_api.py includes skipped test with sqlite segfault note.

- Remediation tasks:
  1. Quarantine flaky tests into a dedicated marker and report.
  2. Add a deterministic alternative test for the same behavior.
  3. Open a tracking issue and define exit criteria to unskip.

- Factory-pattern replacement comment:
  - Replace with factory pattern: No.
  - Reason: Flakiness root cause is execution environment/behavior, not object construction style.

## Delivery Plan (Phased)

### Phase 1 (Security and platform risk)

- Implement Omission 1 and Omission 3 first.
- Deliverables:
  - API permission tests
  - Middleware test suite baseline

### Phase 2 (Feature-area gap)

- Implement Omission 2.
- Deliverables:
  - issue_tracker tests for models/forms/views
  - basic auth/permissions coverage

### Phase 3 (Structure and maintainability)

- Split monolithic files and normalize layout.
- Introduce explicit factory pattern where marked Yes.
- Create common reusable factories for qa/service_log/issue_tracker test domains.

## Suggested First 5 PRs

1. PR-T01: API composite/upload permission test coverage baseline.
2. PR-T02: Middleware login_required + maintain_filters tests.
3. PR-T03: Middleware profiler tests and edge cases.
4. PR-T04: issue_tracker models/forms/view tests with factories.
5. PR-T05: qa/tests/test_views.py first split (composite/upload sections).

## Definition of Done

1. All three omissions have direct tests and negative-path assertions.
2. At least one large test module is split with no behavior loss.
3. Factory pattern is adopted only where marked Yes above.
4. Skipped/flaky critical-path tests have tracking issues and replacement coverage.
