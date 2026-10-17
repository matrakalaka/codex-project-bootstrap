# Proposed `human_approval.v0` Payload — Owner Confirmation Required

This is a proposed payload, not a formal approval artifact. It must not be
validated or consumed as approval until the project owner confirms the exact
bindings and supplies the pending attributable fields. Historical Phase 2A
provenance remains `INCOMPLETE`.

## Verified bindings

- **Repository identity:** `https://github.com/matrakalaka/codex-project-bootstrap.git`
- **Repository path:** `/Users/admin/codex-project-bootstrap-memory-integration`
- **Branch:** `integration/bootstrap-memory-20261017`
- **Authorized HEAD:** `a169c2fe5f6772cc5a7466c889356352ea951e6f`
- **Assessment ID:** `bootstrap-memory-integration-qualification`
- **Assessment hash:** `sha256:46c43c58a58a25f6f4c98224e564d6f41d08ec8470578aba256a640bf273fc65`
- **Correlation ID:** `bootstrap-memory-20261017` (derived from the verified
  branch identifier; owner confirmation required)
- **Task ID:** `bootstrap-memory-integration-qualification` (derived from the
  canonical checkpoint ID; owner confirmation required)
- **Objective hash:** `sha256:c7f153c88728ab7b0dc609a6c04f1667499a4310554ebfb2ae5dac7f744d3319`
- **Hash algorithm:** repository `canonical_hash`: canonical JSON with sorted
  object keys, compact separators, UTF-8 encoding; assessment hash is over the
  assessment object with its self-hash field removed, and objective hash is
  over the exact canonical objective string.

## Proposed contract payload

```json
{
  "schema_version": "human_approval.v0",
  "approval_id": "OWNER_CONFIRMATION_REQUIRED",
  "correlation_id": "bootstrap-memory-20261017",
  "task_id": "bootstrap-memory-integration-qualification",
  "assessment_id": "bootstrap-memory-integration-qualification",
  "assessment_hash": "sha256:46c43c58a58a25f6f4c98224e564d6f41d08ec8470578aba256a640bf273fc65",
  "repository_identity": "https://github.com/matrakalaka/codex-project-bootstrap.git",
  "authorized_head": "a169c2fe5f6772cc5a7466c889356352ea951e6f",
  "objective_hash": "sha256:c7f153c88728ab7b0dc609a6c04f1667499a4310554ebfb2ae5dac7f744d3319",
  "allowed_paths": [
    "GLOBAL_ENGINEERING_STANDARD.md",
    "GLOBAL_PROJECT_BOOTSTRAP.md",
    "prompts/NEW_TASK_START.md",
    "templates/AGENTS_TEMPLATE.md",
    "templates/CONTINUE_TOMORROW_TEMPLATE.md",
    "tests/test_continuity_checkpoint.py",
    "CONTINUE_TOMORROW.md",
    "PHASE_2A_INDEPENDENT_APPROVAL_REVIEW.md",
    "evidence/bootstrap_assessment.v0.json"
  ],
  "forbidden_paths": [
    "README.md",
    ".git/**",
    "/Users/admin/codex-project-bootstrap/**",
    "/Users/admin/UltimateBoxManager/**",
    "production/**",
    "deploy/**",
    "**/secrets/**",
    "**/credentials/**"
  ],
  "approved": true,
  "approver": {
    "type": "HUMAN",
    "identifier": "OWNER_CONFIRMATION_REQUIRED"
  },
  "approved_at": "OWNER_CONFIRMATION_REQUIRED",
  "reason": "OWNER_CONFIRMATION_REQUIRED: approve the exact assessment, objective hash, scope, and HEAD; preserve historical Phase 2A provenance as INCOMPLETE",
  "approval_sequence": 0
}
```

## Pending owner confirmations

The payload cannot be issued as `human_approval.v0` until the owner confirms:

1. the assessment ID, correlation ID, and task ID;
2. the exact assessment hash, objective hash, allowed paths, forbidden paths,
   and authorized HEAD above;
3. a real attributable owner identifier;
4. the approval timestamp and reason; and
5. the initial approval sequence. No predecessor approval record exists in the
   repository, so sequence `1` is the only evidence-based initial candidate,
   but it still requires owner confirmation.

Do not pass this proposed document to the validator as an approval artifact;
its placeholders and sequence `0` are intentionally invalid for issuance.
