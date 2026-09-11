ONE TASK: perform the approved UI/UX redesign scope.

SCOPE:
<surface/phase>

Read:
1. AGENTS.md
2. KNOWN_GOOD_CONTRACTS.md
3. latest relevant CONTINUE_TOMORROW.md checkpoint
4. approved audit/plan
5. UI_STANDARDS.md if present
6. Codebase Memory first where useful

Rules:
- staging/design branch only unless explicitly approved otherwise
- preserve business logic, data contracts, and security boundaries
- use existing design system/shared primitives where possible
- do not silently change workflows
- do not begin the next redesign phase
- protect unrelated dirty work

Validation may include:
- targeted tests
- build
- Playwright rendered validation
- keyboard/focus behavior
- responsive checks
- light/dark checks
- screenshots
- human visual approval for subjective appearance

Do not claim subjective visual PASS solely from source/CSS inspection.

If explicitly approved, proceed end-to-end through routine in-scope actions under AGENTS.md autonomy.

Return a concise report and STOP.
