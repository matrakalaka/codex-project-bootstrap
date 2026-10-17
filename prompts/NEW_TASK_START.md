Start one new scoped engineering task.

Before implementation, read the global `PROJECT_NORTH_STAR.md` resolved by
the bootstrap and any clearly designated project-specific North Star. State
the final intended objective, required proof, explicit out-of-scope work, and
stop/promotion boundary. Keep ordinary engineering obstacles inside this
task; park non-blocking ideas instead of creating phases for them.

Read in this order:

1. AGENTS.md — full
2. KNOWN_GOOD_CONTRACTS.md — full
3. the latest relevant `CONTINUE_TOMORROW.md` checkpoint
4. directly relevant task-specific docs and approved records
5. Codebase Memory first where useful, only if available, operational, and
   correctly scoped

Inspect git status before editing.

Before planning:

- Identify the active repository path and canonical remote, then recover only
  its project-owned checkpoint.
- Recover the latest authoritative checkpoint.
- Validate its repository path or remote identity, branch, validated source
  revision, current observed HEAD, objective, approved scope, status,
  contradictions, freshness, and recorded dirty state against the current
  repository. If the checkpoint revision differs from the current HEAD,
  compare the validated source revision and material source changes before
  accepting freshness; do not accept or reject from the SHA mismatch alone.
- Reject a checkpoint belonging to another repository. Do not import another
  project's objective, decisions, approvals, history, or completion evidence.
- If the checkpoint is missing, do not fall back to another project's memory;
  use only this repository's authority, source, tests, git history, and
  approved records. Label cross-project references non-authoritative unless
  separately approved and verified.
- Confirm the next action is still within the approved objective and scope.
- If the checkpoint is missing, contradictory, stale, or cannot be validated,
  stop with `BLOCKED_PRECONDITION` or `DIVERGENCE` as applicable. Do not infer
  history from chat memory.
- If Codebase Memory is unavailable, mis-scoped, or blocked, record that state
  and use repository authority, git, source, tests, and approved records as the
  safe fallback. Do not restart, reconfigure, reindex, or repoint the daemon.
- Before planning or implementation, classify recovered items as
  `REQUIRED_FOR_OBJECTIVE`, `ALREADY_SATISFIED`, `BLOCKER`, or `PARKED`.
  Do not reopen completed work without new evidence.

TASK:
<ORIGINAL APPROVED OBJECTIVE: describe the exact task>

TARGET:
<INTENDED CHANGE: describe the desired result>

REQUIRED PROOF:
<evidence that proves the objective works>

EXPECTED CHANGE UNIT:
<smallest coherent change and expected changed paths>

CONSTRAINTS:
<OUT OF SCOPE: files/environments/areas that must remain untouched>

NEW DEPENDENCIES REQUIRED: YES / NO / UNKNOWN
EXACT OBJECTIVE REQUIRING EACH DEPENDENCY:
<state the exact objective part and dependency proof, or NONE>

OPTIONAL TOOLING REQUIRED: YES / NO

STOP / PROMOTION BOUNDARY:
<where this task stops and what approval is required next>

Determine the smallest coherent implementation and validation plan.

If this task is already explicitly approved and AGENTS.md autonomy permits execution, proceed end-to-end without repeated routine approval.

Stop only for the explicit stop conditions in AGENTS.md.

Do not begin another task after this one.

Before closeout, make these three engineering checks:
- CORRECTNESS — direct evidence proves the approved behavior works.
- SCOPE AND BLAST RADIUS — changes match the approved objective, with affected behaviors, interfaces, data, and workflows considered.
- SIMPLICITY — the implementation is the smallest coherent safe change, without unnecessary code, abstractions, dependencies, configuration, or documentation.

Return a concise final report:
- result
- files changed
- validation
- objective satisfied
- required verification passed
- changed paths remained approved
- dependency proof existed for any expansion
- unrelated findings were PARKED
- optional tooling did not become scope
- STOP reached
- commit/push/deployment state
- protected areas untouched
- continuity checkpoint written and its status
- one recommended next task, or `STOP_COMPLETE`

Then STOP.
