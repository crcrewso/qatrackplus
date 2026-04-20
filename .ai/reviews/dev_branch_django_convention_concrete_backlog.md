Generated with AI

# Concrete Backlog: Dev Branch Django Convention Remediation

Date: 2026-04-20
Scope basis: [.ai/reviews/dev_branch_django_convention_top10_plan.md](.ai/reviews/dev_branch_django_convention_top10_plan.md)

## Prioritization Model
- P0: security or production integrity risk
- P1: high reliability/performance and near-term upgrade blockers
- P2: structural modernization with medium risk
- P3: larger refactors with high coordination cost

## Epic A: Immediate Security and Access Hardening

### A1 (P0) Externalize and rotate SECRET_KEY
- Problem: hard-coded key in [qatrack/settings.py](qatrack/settings.py#L41)
- Deliverables:
  - Read secret from environment in settings.
  - Fail fast for missing secret when DEBUG is false.
  - Update deployment templates/docs for Linux + Windows + Docker paths.
  - Runbook for key rotation and session invalidation.
- Dependencies: none
- Acceptance criteria:
  - No literal secret in tracked settings.
  - App refuses startup in non-debug if secret is missing.
  - Deployment docs include exact env var examples.
- Estimate: 2 points
- Suggested PR: PR-01

### A2 (P0) Make DRF permission intent explicit
- Problem: empty permission classes in [qatrack/api/qa/views.py](qatrack/api/qa/views.py#L17)
- Deliverables:
  - Replace [] with explicit policy (AllowAny or IsAuthenticated/Scoped permission) per endpoint.
  - Add endpoint-level comment/docstring justifying policy.
  - Add API tests confirming expected unauthenticated/authenticated outcomes.
- Dependencies: none
- Acceptance criteria:
  - No empty permission_classes remain in API views.
  - Tests enforce intended access model.
- Estimate: 3 points
- Suggested PR: PR-02

## Epic B: Reliability and Data Integrity Quick Wins

### B1 (P1) Replace broad exception catches in unit schedule handlers
- Problem: broad catches in [qatrack/units/views.py](qatrack/units/views.py#L63)
- Deliverables:
  - Replace catch-all exceptions with specific types.
  - Add warning logs with context where fallback behavior is intentional.
  - Add tests for invalid timezone/day payload handling.
- Dependencies: none
- Acceptance criteria:
  - No bare/broad Exception catch in target handlers.
  - Invalid payload tests pass and unexpected errors bubble correctly.
- Estimate: 2 points
- Suggested PR: PR-03

### B2 (P1) Add transaction boundaries for grouped writes
- Problem: schedule mutation handlers not atomic at [qatrack/units/views.py](qatrack/units/views.py#L57)
- Deliverables:
  - Wrap grouped writes in transaction.atomic.
  - Add rollback test by forcing mid-operation exception.
- Dependencies: none (can merge with B1 if desired)
- Acceptance criteria:
  - Partial-write scenarios rollback completely.
- Estimate: 2 points
- Suggested PR: PR-04

### B3 (P1) Remove N+1 lookup in unit edit flow
- Problem: repeated get in list comp at [qatrack/units/views.py](qatrack/units/views.py#L120)
- Deliverables:
  - Replace per-id get with one bulk fetch (filter/in_bulk).
  - Add query-count assertion test on typical multi-unit payload.
- Dependencies: none
- Acceptance criteria:
  - Query count stays bounded for 1..N unit inputs.
- Estimate: 2 points
- Suggested PR: PR-05

## Epic C: URL and Schema Modernization

### C1 (P1) URLConf modernization: path/re_path cleanup
- Problem: widespread alias pattern from re_path as url in [qatrack/urls.py](qatrack/urls.py#L2)
- Deliverables:
  - Convert simple regex routes to path.
  - Keep only true regex routes on explicit re_path.
  - Remove alias imports and standardize module style.
  - Run reverse-resolution regression tests.
- Dependencies: none
- Acceptance criteria:
  - No re_path-as-url alias remains.
  - Route tests and major navigational smoke tests pass.
- Estimate: 8 points
- Suggested PRs: PR-06 (core urls), PR-07 (qa + service_log), PR-08 (api + remaining apps)

### C2 (P1) Migrate unique_together to named UniqueConstraint
- Problem: legacy uniqueness meta across models like [qatrack/units/models.py](qatrack/units/models.py#L171)
- Deliverables:
  - Replace unique_together with Meta.constraints + named UniqueConstraint.
  - Generate and verify migrations in app slices.
  - Validate uniqueness behavior parity with tests.
- Dependencies: none
- Acceptance criteria:
  - No runtime model uses unique_together.
  - Constraints carry deterministic names.
- Estimate: 8 points
- Suggested PRs: PR-09 (units + parts), PR-10 (qa + service_log)

### C3 (P2) Convert direct User model relations to AUTH_USER_MODEL references
- Problem: direct auth.User coupling, e.g. [qatrack/attachments/models.py](qatrack/attachments/models.py#L11)
- Deliverables:
  - Replace direct User imports and model FKs with settings.AUTH_USER_MODEL/get_user_model patterns.
  - Add migration updates where required.
  - Verify admin/forms/serializers/test fixtures compatibility.
- Dependencies: C2 preferred first (reduces overlapping migration churn)
- Acceptance criteria:
  - No model relation imports django.contrib.auth.models.User for FK definitions.
- Estimate: 5 points
- Suggested PR: PR-11

## Epic D: JSON and Attachment Model Refactors

### D1 (P2) Migrate custom JSON TextField shim to native JSONField
- Problem: custom class in [qatrack/qatrack_core/fields.py](qatrack/qatrack_core/fields.py#L7)
- Deliverables:
  - Inventory every custom JSONField usage.
  - Introduce staged migrations per app converting to models.JSONField.
  - Data cleanup migration for malformed JSON rows before schema swap.
  - Remove shim once all consumers are migrated.
- Dependencies: C2/C3 done first (reduce model migration conflicts)
- Acceptance criteria:
  - No runtime model field uses qatrack_core.fields.JSONField.
  - JSON data round-trips in all supported DB engines.
- Estimate: 8 points
- Suggested PRs: PR-12 (inventory + first app), PR-13 (remaining apps + shim removal)

### D2 (P3) Redesign attachment ownership model
- Problem: multi-nullable owner FKs in [qatrack/attachments/models.py](qatrack/attachments/models.py#L97)
- Deliverables:
  - ADR choosing GenericForeignKey vs normalized subtype design.
  - New schema + migration strategy (backfill + dual-write window if needed).
  - Update owner resolution, validation, admin, API serializers, and upload paths.
  - Add integrity constraints to enforce exactly one owner target.
- Dependencies: D1 preferred first; also coordinate with API/auth teams
- Acceptance criteria:
  - Exactly one owner relation is enforceable at model/data level.
  - Existing attachments migrated and accessible with zero data loss.
- Estimate: 13 points
- Suggested PRs: PR-14 (ADR + scaffolding), PR-15 (migration + app cutover), PR-16 (cleanup)

## Suggested PR Sequence (Concrete)
1. PR-01 A1 Secret key externalization + docs
2. PR-02 A2 DRF permission explicitness + tests
3. PR-03 B1 Exception narrowing + tests
4. PR-04 B2 Atomic transactions + rollback tests
5. PR-05 B3 N+1 elimination + query-count tests
6. PR-06 C1 urls core conversion
7. PR-07 C1 qa/service_log conversion
8. PR-08 C1 api/remaining app conversion
9. PR-09 C2 unique constraints (units/parts)
10. PR-10 C2 unique constraints (qa/service_log)
11. PR-11 C3 AUTH_USER_MODEL alignment
12. PR-12 D1 JSONField migration phase 1
13. PR-13 D1 JSONField migration phase 2 + shim removal
14. PR-14 D2 Attachment redesign ADR + schema scaffold
15. PR-15 D2 data migration and runtime cutover
16. PR-16 D2 legacy fields removal + hardening

## Dependency Graph (Simplified)
- A1, A2, B1, B2, B3: independent; parallelizable
- C1 independent; can run in parallel with B-epic
- C2 before C3 preferred
- C2/C3 before D1 preferred (migration conflict minimization)
- D1 before D2 preferred

## Sprint Packaging (2-week sprints)
- Sprint 1: PR-01..PR-05 (all quick wins)
- Sprint 2: PR-06..PR-08 (URL modernization)
- Sprint 3: PR-09..PR-11 (constraints + auth model alignment)
- Sprint 4: PR-12..PR-13 (JSON migration)
- Sprint 5-6: PR-14..PR-16 (attachment redesign)

## Definition of Done (Program-Level)
- Security: no committed secret material; explicit API access intent
- Reliability: no broad exception masking in schedule flows; grouped writes are atomic
- Performance: no N+1 in targeted schedule edit path
- Django conventions: routing style modernized; uniqueness uses UniqueConstraint; user model is swappable-compatible
- Data model integrity: native JSONField usage complete; attachment ownership guarantees exactly one owner

## Risks and Mitigations
- Migration conflicts across parallel PRs
  - Mitigation: lock migration ownership per sprint/app and rebase gate before merge
- Cross-database JSON behavior variance
  - Mitigation: matrix test on sqlite/postgres/mysql/mssql for D1
- Attachment redesign blast radius
  - Mitigation: ADR first, dual-read compatibility period, rollback script
