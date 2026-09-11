# GLOBAL PROJECT BOOTSTRAP STANDARD

## PURPOSE
Use a consistent engineering, governance, documentation, validation, and handoff structure for future projects.

This is a default. It does not override existing project authority.

## 1. CORE PROJECT FILES
For substantial projects, normally establish:
- AGENTS.md
- KNOWN_GOOD_CONTRACTS.md
- CONTINUE_TOMORROW.md

Add when justified:
- ARCHITECTURE.md
- WORKFLOW_RULES.md
- UI_STANDARDS.md
- docs/plans/
- docs/audits/
- docs/decisions/

Do not create documentation without a clear purpose.

## 2. AUTHORITY HIERARCHY
Unless an existing project defines a stronger order:
1. AGENTS.md
2. KNOWN_GOOD_CONTRACTS.md
3. latest relevant CONTINUE_TOMORROW.md checkpoint
4. approved task-specific plans/specs/audits
5. ARCHITECTURE.md / WORKFLOW_RULES.md / UI_STANDARDS.md
6. source and tests
7. Codebase Memory
8. Skylos/advisory skills
9. external toolbox resources

Source truth wins when indexed/advisory information is stale.

## 3. FIRST CONTACT WITH A PROJECT
Start READ-ONLY.

Inspect:
- repository structure
- README
- dependency manifests
- existing governance/docs
- architecture
- tests
- git status
- branches/remotes
- deployment model
- database model if relevant
- existing AGENTS.md / CLAUDE.md or similar
- installed tooling

Use Codebase Memory first where appropriate.

Do not modify files during discovery.

## 4. BOOTSTRAP DECISION
If equivalent governance already exists, integrate with it.

Do not overwrite good project conventions.

If missing, propose the minimum required project-local files.

## 5. KNOWN-GOOD BASELINE
Before large changes, establish what currently works using evidence such as:
- tests
- builds
- runtime behavior
- screenshots
- database/API checks
- documented contracts

Record important proven behavior in KNOWN_GOOD_CONTRACTS.md.

## 6. ONE TASK PER SESSION
One meaningful engineering task per Codex session.

When the approved task is complete, STOP.

Never automatically start the next task.

## 7. AUTONOMY AFTER EXPLICIT TASK APPROVAL
Once the user explicitly approves a scoped task, Codex may complete the normal reversible actions required for that exact task without repeatedly asking permission.

This can include:
- editing approved files
- targeted tests/builds
- approved Playwright validation
- explicitly approved dependency installation
- local test artifacts
- scoped commit
- approved non-production push
- approved staging verification

STOP for:
- scope expansion
- unapproved file changes
- production access/writes
- unapproved main changes
- unapproved DB/schema/migration/RLS/RPC changes
- destructive/irreversible operations
- secrets/security changes
- antivirus/security warnings
- ambiguous target environment
- unrelated dirty-work conflicts
- unexpected known-good contract changes
- evidence contradicting the plan

## 8. TOKEN-EFFICIENT EXECUTION
- read authority once per session unless relevant files change
- do not repeatedly reread the same markdown
- use Codebase Memory first where appropriate
- inspect only task-relevant files
- use bounded searches
- avoid broad audits unless needed
- avoid giant logs/diffs
- summarize evidence
- do not rerun successful validation without reason
- do not re-plan approved work without new evidence
- do not repeatedly ask routine approvals
- stop immediately when the task is complete

## 9. DIRTY WORKTREE PROTECTION
Inspect git status before editing.

Treat pre-existing dirty/untracked work as protected.

Do not restore, overwrite, format, stage, or commit unrelated work.

If isolation cannot be proven, STOP.

## 10. IMPLEMENTATION
Prefer the smallest coherent root-cause solution.

Avoid:
- unrelated refactors
- broad cleanup
- speculative abstractions
- unnecessary dependency changes
- architecture rewrites
- out-of-scope edits

## 11. VALIDATION
Use the smallest meaningful evidence set:
- targeted tests
- integration tests
- static/type checks
- lint
- build
- Playwright
- API/database assertions
- staging verification

Escalate only when risk warrants it.

## 12. UI / PLAYWRIGHT
For frontend projects, Playwright + Chromium is the preferred initial rendered/E2E stack when needed.

Use it for:
- smoke tests
- keyboard/focus behavior
- dialog semantics
- responsive regressions
- light/dark checks
- screenshots
- E2E workflows

Playwright does not replace human approval of subjective visual quality.

## 13. STAGING-FIRST UI WORK
Preferred lifecycle:
AUDIT
→ PLAN
→ IMPLEMENT ON STAGING
→ TEST
→ PLAYWRIGHT / RENDERED VALIDATION
→ HUMAN REVIEW
→ PRODUCTION READINESS
→ EXPLICIT PRODUCTION APPROVAL

Staging approval does not equal production approval.

## 14. DEPENDENCIES
Before adding one:
- prove the need
- prefer official sources
- prefer project-local installation
- inspect lockfile impact
- avoid unrelated upgrades
- preserve security controls

Never disable antivirus/security controls to make tooling work.

## 15. DATABASE SAFETY
Database/schema/migration/RLS/RPC work requires explicit scope.

Always identify the exact environment before writes.

Never infer production permission from staging permission.

## 16. PRODUCTION SAFETY
Main and production are protected by default.

Do not merge, push main, deploy production, change production configuration, apply production migrations, or mutate production data without explicit authorization.

## 17. COMMIT DISCIPLINE
Before commit:
- inspect exact diff
- inspect staged files
- exclude unrelated work
- confirm required validation

One coherent task per commit.

## 18. HANDOFF
When appropriate, update CONTINUE_TOMORROW.md with:
- what changed
- validation
- commit/deployment state
- blockers
- exact recommended next task

Do not turn it into a transcript.

## 19. FAILURE CLASSIFICATIONS
PASS — completed and validated.

BLOCKED_PRECONDITION — required condition/tool/access/approval missing.

FAILED_AFTER_EXECUTION — approved execution occurred but validation failed.

DIVERGENCE — protected boundary crossed, wrong environment targeted, or execution contradicted the approved plan.

STOP immediately on DIVERGENCE.

## 20. FINAL PRINCIPLE
Maximum useful progress with:
- minimum unnecessary work
- minimum token waste
- minimum regression risk
- clear evidence
- strict project boundaries
