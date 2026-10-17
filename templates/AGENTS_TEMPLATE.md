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
3. Identify the active repository path and canonical remote.
4. Recover only this repository's canonical CONTINUE_TOMORROW.md checkpoint.
5. Validate repository path/remote ownership, branch, validated source
   revision, current observed HEAD, original objective, approved scope, status,
   recorded dirty state, contradictions, and staleness before planning. If the
   checkpoint revision differs from HEAD, verify material source changes rather
   than accepting or rejecting from the SHA mismatch alone.
6. Reject foreign-project checkpoints. Never import another project's memory.
   If this checkpoint is missing, use only this repository's authority, source,
   tests, git history, and approved records.
7. Read directly relevant task docs and approved records.
8. Use Codebase Memory first where useful only when it is available,
   operational, and correctly scoped.
9. Inspect git status before editing.

If the checkpoint is missing, contradictory, stale, or cannot be validated,
stop with the applicable governed outcome. Do not infer project history from
chat memory. If Codebase Memory is unavailable, mis-scoped, or blocked, record
that state and use repository authority, git, source, tests, and approved
records as fallback. Never restart, reconfigure, reindex, or repoint a memory
daemon during recovery.

Before planning or implementation, classify recovered items as
`REQUIRED_FOR_OBJECTIVE`, `ALREADY_SATISFIED`, `BLOCKER`, or `PARKED`.
Do not reopen `ALREADY_SATISFIED` work without new evidence. Cross-project
references are non-authoritative context unless separately approved and
verified.

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
At every governed task closeout, after parent acceptance, update the single
canonical CONTINUE_TOMORROW.md checkpoint with the original objective/source,
repository path/remote, branch and HEAD, approved/protected scope, binding decisions,
verified completed work, evidence, failed approaches/blockers, current status,
contradictions/staleness, Codebase Memory fallback state, and one next approved
action or STOP_COMPLETE.

The checkpoint is a concise projection of authoritative records, not a second
authority or transcript. Do not create duplicate memory records. If status is
STOP_COMPLETE, do not recommend or begin another task.

## FAILURE CLASSIFICATION
Use:
- PASS
- BLOCKED_PRECONDITION
- FAILED_AFTER_EXECUTION
- DIVERGENCE

STOP immediately on DIVERGENCE.
