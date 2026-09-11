ONE TASK: diagnose and fix this bug.

BUG:
<describe bug>

EXPECTED:
<expected behavior>

Read:
1. AGENTS.md
2. KNOWN_GOOD_CONTRACTS.md
3. latest relevant CONTINUE_TOMORROW.md checkpoint
4. relevant task docs
5. Codebase Memory first where useful

Requirements:
- establish evidence before editing
- identify root cause
- make the smallest coherent fix
- protect unrelated dirty work
- no unrelated cleanup/refactor
- add/update targeted regression coverage where justified
- use the smallest meaningful validation set
- preserve known-good contracts
- do not touch production/main/database unless explicitly approved

If explicitly approved, complete routine in-scope actions end-to-end under AGENTS.md autonomy.

Return:

BUG FIX:
PASS / FAIL / PARTIAL / BLOCKED

Root Cause:
<concise>

Files Changed:
<list>

Validation:
<results>

Known-Good Contracts Preserved:
YES / NO

Commit:
<SHA / NOT COMMITTED>

Push:
YES / NO

Recommended Next Step:
<one exact next step>

Then STOP.
