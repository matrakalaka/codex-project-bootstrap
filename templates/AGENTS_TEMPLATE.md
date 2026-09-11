# AGENTS.md

## PURPOSE
Defines how Codex operates inside this repository.

## AUTHORITY ORDER
1. AGENTS.md
2. KNOWN_GOOD_CONTRACTS.md
3. latest relevant CONTINUE_TOMORROW.md checkpoint
4. approved task-specific plans/specs/audits
5. ARCHITECTURE.md / WORKFLOW_RULES.md / UI_STANDARDS.md
6. source and tests
7. Codebase Memory
8. advisory tools/skills
9. external toolbox resources

Source truth wins when advisory/indexed information is stale.

## SESSION START
1. Read AGENTS.md in full.
2. Read KNOWN_GOOD_CONTRACTS.md.
3. Read only the latest relevant CONTINUE_TOMORROW.md checkpoint.
4. Read directly relevant task docs.
5. Use Codebase Memory first where useful.
6. Inspect git status before editing.

Do not repeatedly reread unchanged authority files in the same session.

## ONE TASK PER SESSION
Perform one meaningful engineering task per session.

When complete: STOP.

Do not automatically begin the next task.

## SCOPED TASK MODE
Before editing, identify:
- exact task goal
- expected file scope
- known-good contracts at risk
- required validation
- protected environments

Do not modify unrelated files.

## AUTONOMY AFTER EXPLICIT TASK APPROVAL
Once the user explicitly approves a scoped task, complete normal reversible in-scope actions without repeatedly asking permission.

This may include:
- editing approved files
- tests/builds
- approved Playwright validation
- explicitly approved dependency installation
- local test artifacts
- scoped commit
- approved non-production push
- approved staging verification

STOP for:
- scope expansion
- unapproved files
- production
- unapproved main changes
- unapproved DB/schema/migration/RLS/RPC changes
- destructive/irreversible actions
- secrets/security changes
- antivirus/security warnings
- ambiguous target
- dirty-work conflicts
- unexpected known-good contract changes
- evidence contradicting the plan

## TOKEN-EFFICIENT EXECUTION
- read authority once per session unless relevant files change
- use Codebase Memory first where appropriate
- inspect task-relevant files only
- use bounded searches
- avoid broad audits without reason
- avoid giant logs/diffs
- summarize evidence
- do not rerun successful validation without reason
- do not repeatedly ask routine approvals
- stop immediately when task is complete

## DIRTY WORKTREE
Treat all pre-existing dirty/untracked work as protected.

Do not restore, overwrite, format, stage, or commit unrelated work.

If isolation cannot be proven, STOP.

## KNOWN-GOOD PRESERVATION
Do not silently regress KNOWN_GOOD_CONTRACTS.md.

If an approved task intentionally changes a contract, update it explicitly with evidence.

## TESTING
Use the smallest meaningful validation set:
- targeted tests
- integration tests
- type/static checks
- lint
- build
- Playwright
- API/database checks
- staging verification

## DEPENDENCIES
Prefer official, project-local, minimal installs.

Do not disable antivirus/security controls.

## DATABASE SAFETY
DB/schema/migration/RLS/RPC work requires explicit scope and exact environment identification.

Never infer production permission from staging permission.

## PRODUCTION / MAIN
Protected by default.

Do not merge, push, deploy, migrate, mutate, or alter production configuration without explicit authorization.

## COMMIT / PUSH
Before commit:
- inspect exact diff
- inspect staged files
- exclude unrelated work
- confirm validation

One coherent task per commit.

Push only the approved branch.

## HANDOFF
When appropriate, update CONTINUE_TOMORROW.md with:
- what changed
- validation
- commit/deployment state
- blockers
- one recommended next task

## FAILURE CLASSIFICATION
Use:
- PASS
- BLOCKED_PRECONDITION
- FAILED_AFTER_EXECUTION
- DIVERGENCE

STOP immediately on DIVERGENCE.
