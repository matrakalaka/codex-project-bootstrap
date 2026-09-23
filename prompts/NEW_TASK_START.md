Start one new scoped engineering task.

Before implementation, read the global `PROJECT_NORTH_STAR.md` resolved by
the bootstrap and any clearly designated project-specific North Star. State
the final intended objective, required proof, explicit out-of-scope work, and
stop/promotion boundary. Keep ordinary engineering obstacles inside this
task; park non-blocking ideas instead of creating phases for them.

Read in this order:

1. AGENTS.md — full
2. KNOWN_GOOD_CONTRACTS.md — full
3. only the latest relevant checkpoint in CONTINUE_TOMORROW.md
4. directly relevant task-specific docs
5. Codebase Memory first where useful

Inspect git status before editing.

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
- recommended next task

Then STOP.
