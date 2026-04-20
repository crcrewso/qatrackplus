Generated with AI

# Proposed Future Branch Split for AI Pending Artifacts

Date: 2026-04-20
Source: GitHub commit comment on `35bfdf793f9a97f7886c2fa859d86bf70006eadf`

## Rationale

The `chore/ai-pending-artifacts` commit intentionally consolidated current AI-generated planning and modernization artifacts so they could be reviewed together once. Future implementation and review work should be split into smaller branches with clearer scope boundaries.

## Proposed Follow-On Branches

### 1. `docs/v4-install-and-support-updates`
- Carry user-facing documentation refreshes in:
  - `docs/index.rst`
  - `docs/developer/guide.rst`
  - `docs/developer/schema.rst`
  - `docs/tutorials/internationalization/add_language.rst`
  - `docs/conf.py`
- Goal: release-facing documentation accuracy, support channel updates, and schema generation guidance.

### 2. `chore/deploy-apache-templates`
- Carry:
  - `deploy/apache/apache24_linux.conf`
  - `deploy/apache/apache24_windows.conf`
- Goal: isolate deployment-template review from application logic and broader documentation churn.

### 3. `docs/django-upgrade-plans`
- Carry:
  - `docs/developer/django42_migration_plan.md`
  - `docs/developer/django52_migration_plan.md`
  - `.ai/plans/django42_migration_plan.md`
  - `.ai/plans/django52_migration_plan.md`
- Goal: separate framework-upgrade planning from general product documentation.

### 4. `docs/test-remediation-and-audits`
- Carry:
  - `.ai/reviews/documentation_audit.md`
  - `.ai/reviews/dev_branch_django_convention_top10_plan.md`
  - `.ai/reviews/dev_branch_django_convention_concrete_backlog.md`
  - `.ai/reviews/test_suite_remediation_plan.md`
- Goal: keep audit outputs and prioritized remediation plans together.

### 5. `chore/project-tracking-artifacts`
- Carry:
  - `.ai/github/project6_backlog_drafts_added.md`
  - `.ai/github/assigned_issues.md`
  - `.ai/github/issue_713_detailed_analysis.md`
  - `.ai/chat/2026-04-20_assistant_responses.md`
  - `.ai/README.md`
- Goal: preserve session/project tracking without coupling it to runtime or docs changes.

### 6. `chore/dependency-metadata-followup`
- Carry:
  - `pyproject.toml`
- Goal: review package metadata changes independently after confirming they are intended separately from the docs work.

## Recommended Merge Order

1. Deploy templates and user-facing docs.
2. Django upgrade plans and audits.
3. Project-tracking artifacts and package metadata.

## Notes

- No tests were run for the artifact branch.
- This file mirrors the GitHub comment so the recommendation remains available in-repo even if the commit comment is later overlooked.