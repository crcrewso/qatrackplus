Generated with AI

# Dev Branch Django Convention Review: Top 10 High-Impact Gaps

Date: 2026-04-20
Branch reviewed: Dev

Scoring used:
- Impact: 1 (low) to 5 (critical)
- Effort: S, M, L
- Priority rank is impact-first, then upgrade/security urgency

## Ranked Findings

1. Hard-coded project secret key in source control
- Why non-conventional: Django expects deployment-specific secrets from environment or secret store, not committed values.
- Impact: 5 (critical security)
- Evidence: [qatrack/settings.py](qatrack/settings.py#L41)
- Risk: Session and token forgery risk if leaked; weak operational security posture.
- Fix: Read secret from environment and fail fast when missing in non-debug.
- Effort: S

2. URLConf uses legacy url aliasing pattern broadly
- Why non-conventional: Modern Django routing prefers path and explicit re_path. Aliasing re_path as url keeps legacy semantics and obscures intent.
- Impact: 5 (major upgrade/maintenance)
- Evidence: [qatrack/urls.py](qatrack/urls.py#L2), [qatrack/qa/urls.py](qatrack/qa/urls.py#L1), [qatrack/service_log/urls.py](qatrack/service_log/urls.py#L1)
- Risk: Higher upgrade friction and brittle regex-heavy routes.
- Fix: Convert simple routes to path; keep explicit re_path only where needed.
- Effort: M-L

3. Multiple models still use unique_together meta option
- Why non-conventional: Current Django convention is explicit UniqueConstraint entries under Meta.constraints.
- Impact: 4 (upgrade and schema clarity)
- Evidence: [qatrack/units/models.py](qatrack/units/models.py#L171), [qatrack/qa/models.py](qatrack/qa/models.py#L1398), [qatrack/parts/models.py](qatrack/parts/models.py#L104), [qatrack/service_log/models.py](qatrack/service_log/models.py#L89)
- Risk: Lower constraint expressiveness and future migration complexity.
- Fix: Replace unique_together with named UniqueConstraint definitions and migrations.
- Effort: M

4. Custom JSON field implemented as TextField serializer shim
- Why non-conventional: Django provides native JSONField with better DB support, validation, and query semantics.
- Impact: 4 (data correctness and portability)
- Evidence: [qatrack/qatrack_core/fields.py](qatrack/qatrack_core/fields.py#L7), usage in [qatrack/qa/models.py](qatrack/qa/models.py#L27), [qatrack/service_log/models.py](qatrack/service_log/models.py#L16)
- Risk: Inconsistent JSON behavior and weaker DB-level capabilities.
- Fix: Migrate legacy custom JSON fields to models.JSONField with staged data migration.
- Effort: M-L

5. Direct coupling to auth User model instead of swappable auth user reference
- Why non-conventional: Django convention is settings.AUTH_USER_MODEL for relations to preserve custom user compatibility.
- Impact: 4 (extensibility and migration risk)
- Evidence: [qatrack/attachments/models.py](qatrack/attachments/models.py#L11), [qatrack/attachments/models.py](qatrack/attachments/models.py#L107), [qatrack/qa/models.py](qatrack/qa/models.py#L633), [qatrack/issue_tracker/models.py](qatrack/issue_tracker/models.py#L3)
- Risk: Difficult future adoption of custom auth user model.
- Fix: Replace ForeignKey(User, ...) with ForeignKey(settings.AUTH_USER_MODEL, ...), create migrations, and update imports.
- Effort: M-L

6. Attachment ownership modeled with many nullable foreign keys
- Why non-conventional: Django polymorphic ownership convention is GenericForeignKey or explicit normalized relations, not many optional owner columns.
- Impact: 4 (data integrity and complexity)
- Evidence: [qatrack/attachments/models.py](qatrack/attachments/models.py#L97), [qatrack/attachments/models.py](qatrack/attachments/models.py#L121), [qatrack/attachments/models.py](qatrack/attachments/models.py#L125)
- Risk: Ambiguous ownership states, difficult constraints, higher bug surface.
- Fix: Move to GenericForeignKey or redesigned owner-specific attachment models with strict constraints.
- Effort: L

7. Exception handling is overly broad in schedule endpoints
- Why non-conventional: Catching Exception masks programming and data errors; convention is specific exception classes.
- Impact: 3 (debuggability and correctness)
- Evidence: [qatrack/units/views.py](qatrack/units/views.py#L63), [qatrack/units/views.py](qatrack/units/views.py#L115), [qatrack/units/views.py](qatrack/units/views.py#L124), [qatrack/units/views.py](qatrack/units/views.py#L166)
- Risk: Silent failure patterns and hard-to-trace runtime defects.
- Fix: Catch explicit exceptions (for example ZoneInfoNotFoundError, ValueError, ObjectDoesNotExist where expected) and log actionable context.
- Effort: S

8. N+1 query pattern in unit edit handler
- Why non-conventional: Repeated get in a list comprehension issues one query per unit id.
- Impact: 3 (performance under scale)
- Evidence: [qatrack/units/views.py](qatrack/units/views.py#L120)
- Risk: Latency spikes for larger unit batches and avoidable DB load.
- Fix: Use filter(id__in=...) with in_bulk or dict mapping in one query.
- Effort: S

9. Multi-record write endpoints are not wrapped in transaction atomic blocks
- Why non-conventional: Django convention for grouped writes is transaction.atomic to avoid partial persistence.
- Impact: 3 (data consistency)
- Evidence: [qatrack/units/views.py](qatrack/units/views.py#L57), [qatrack/units/views.py](qatrack/units/views.py#L110)
- Risk: Partial updates on mid-request errors.
- Fix: Apply transaction.atomic around write sequences and associated object updates.
- Effort: S

10. DRF API views use empty permission_classes lists
- Why non-conventional: Explicit AllowAny or project default permission classes are preferred for readability and intent.
- Impact: 3 (security clarity)
- Evidence: [qatrack/api/qa/views.py](qatrack/api/qa/views.py#L17), [qatrack/api/qa/views.py](qatrack/api/qa/views.py#L21)
- Risk: Ambiguous access policy and accidental overexposure as defaults evolve.
- Fix: Set explicit permission classes per endpoint and document expected auth behavior.
- Effort: S

## Prioritized Fix Plan

## Phase 0: Immediate hardening (same sprint)
1. Secret key externalization and deployment secret rotation
- Covers finding 1
- Outcome: removes highest-severity security debt immediately

2. Lock down API permission intent
- Covers finding 10
- Outcome: explicit auth stance and fewer policy surprises

## Phase 1: Fast reliability and consistency wins (1-3 days)
3. Replace broad exception handlers with specific exceptions and structured logging
- Covers finding 7

4. Remove N+1 query in unit edit handler using bulk retrieval
- Covers finding 8

5. Add transaction.atomic around schedule mutation endpoints
- Covers finding 9

## Phase 2: Django modernization pass (1-2 weeks)
6. Route modernization sweep from url alias style to path/re_path split
- Covers finding 2

7. unique_together conversion to named UniqueConstraint entries
- Covers finding 3

8. AUTH_USER_MODEL alignment for model relations
- Covers finding 5

## Phase 3: Data model modernization (2-4 weeks)
9. Migrate custom JSON TextField usage to native JSONField
- Covers finding 4
- Plan: inventory -> migration design -> rollout by app boundary

10. Redesign attachment ownership model
- Covers finding 6
- Plan: GenericForeignKey or normalized subtype ownership, with migration and integrity checks

## Suggested Execution Order by Impact and Risk
1) 1
2) 10
3) 7
4) 9
5) 8
6) 2
7) 3
8) 5
9) 4
10) 6

## Acceptance Criteria
- Security:
  - No secret material in source settings
  - Explicit permissions for API views
- Reliability:
  - No broad Exception catches in schedule handlers
  - Atomic behavior for grouped writes
- Performance:
  - Unit edit path executes bounded query count for large unit batches
- Modernization:
  - URLConf no longer uses re_path alias as url for simple routes
  - Model uniqueness represented with UniqueConstraint
  - User references use AUTH_USER_MODEL
  - Legacy JSON field shim retired where feasible
  - Attachment ownership has enforceable single-owner semantics
