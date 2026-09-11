ONE TASK: perform a READ-ONLY production-readiness assessment.

Do NOT deploy production.
Do NOT merge or push main.
Do NOT apply production migrations.
Do NOT mutate production data.

Read:
1. AGENTS.md
2. KNOWN_GOOD_CONTRACTS.md
3. latest relevant CONTINUE_TOMORROW.md checkpoint
4. approved implementation/validation plan
5. relevant architecture/workflow docs
6. Codebase Memory first where useful

Assess:
- exact diff intended for production
- test/build status
- staging evidence
- known-good contract impact
- database/migration requirements
- environment separation
- rollback path
- production identity checks
- required cleanup
- remaining manual approvals

Return:

PRODUCTION READINESS:
YES / NO / BLOCKED

Exact Production Diff:
<summary>

Tests:
<status>

Build:
<status>

Staging Validation:
<status>

Database Changes Required:
YES / NO

Migration Status:
<status>

Rollback:
<status>

Known-Good Contract Impact:
<summary>

Remaining Risks:
<list>

Exact Production Runbook:
<numbered high-level steps>

Safe To Request Production Approval:
YES / NO

Then STOP.
