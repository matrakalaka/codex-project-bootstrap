# CONTINUE_TOMORROW.md

## PURPOSE
Canonical concise handoff between sessions.

This is the single continuity checkpoint for the governed task. It is a
projection of authoritative project files, tests, approvals, and git evidence;
it does not replace or compete with those sources.

Read and validate the latest relevant checkpoint before planning a new task.
Read older records only when the checkpoint identifies an unresolved conflict
or when the authoritative source cannot answer the question.

Do not use this file as a transcript.

# LATEST CHECKPOINT

**Checkpoint ID:** <stable task/checkpoint identifier>
**Date:** <YYYY-MM-DD>
**Task:** <short task>
**Original Objective:** <the objective that remains in force for this task>
**Objective Source:** <task packet, approved prompt, plan, or other authority reference>
**Repository Identity:** <canonical repository path or remote identity>
**Repository Remote:** <canonical remote URL, or NOT RECORDED>
**HEAD (Validated Source Revision):** <full commit SHA validated for the source>
**Checkpoint Revision:** <checkpoint version identifier; may be UNCOMMITTED>
**Current Observed HEAD:** <full commit SHA observed when this checkpoint was written>
**Branch:** <branch>
**Worktree State:** CLEAN / DIRTY — <summary of protected uncommitted or untracked work>
**Material Source Changes Since Validation:** <NONE / exact paths and evidence>
**Dirty-Worktree Evidence:** <status/diff evidence and protected paths>
**Environment:** <local/staging/production/etc.>
**Status:** ACTIVE / PASS / PARTIAL / BLOCKED / FAILED / STOP_COMPLETE / CONTRADICTORY

## Approved Scope
- **Allowed paths / surfaces:** <exact bounded scope>
- **Forbidden paths / environments:** <protected scope>
- **Approval reference:** <approval, task packet, or HUMAN_APPROVAL reference>

## Binding Decisions
- <decision>: <authority/source reference and rationale>

## Verified Completed Work
- <completed item>: <evidence reference>

## Evidence References
- <test, build, runtime, commit, receipt, or authoritative document reference>

## Failed Approaches and Blockers
- <approach or blocker>: <observed result and evidence reference>
- Write `NONE RECORDED` when no failed approach or blocker exists.

## Validation Summary
- <test/check>: PASS / FAIL / NOT_RUN — <evidence reference>

## Commit / Deployment
- Commit: <SHA / NOT COMMITTED>
- Push: YES / NO
- Deployment: <status>

## Protected / Untouched
- <main/production/database/etc.>
- <unrelated dirty work>

## Contradictions and Staleness
- **State:** NONE / PRESENT
- **Details:** <conflicting authority, stale HEAD, stale evidence, or UNKNOWN state>
- **Required resolution:** <exact next governed action, or NONE>

## Recovery Classification
- **Required for objective:** <items still required>
- **Already satisfied:** <verified completed items not to reopen without new evidence>
- **Blockers:** <current blockers>
- **Parked:** <explicitly deferred items>

## Codebase Memory Fallback
- **State:** OPERATIONAL / UNAVAILABLE / MIS-SCOPED / BLOCKED / NOT_REQUIRED
- **Fallback used:** <repository authority, git, tests, or other safe source>
- Do not restart, reconfigure, reindex, or repoint a memory daemon as part of
  checkpoint recovery.

## Next Approved Action
<one exact bounded next action, or STOP_COMPLETE>

## ChatGPT / Codex Handoff Projection
<concise evidence-backed projection for a handoff where ChatGPT cannot access
the local repository automatically; identify this repository, objective,
status, completed work, decisions, blockers, protected boundaries, next action,
evidence/freshness, and remaining uncertainties.>

## Stop
At governed task closeout, record the checkpoint only after the parent outcome
is accepted. Do not automatically begin another task. If the current status is
`STOP_COMPLETE`, the next approved action must be `STOP_COMPLETE`.
