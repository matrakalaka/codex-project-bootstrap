# GLOBAL PROJECT BOOTSTRAP STANDARD

## PURPOSE
Use a consistent engineering, governance, documentation, validation, and handoff structure for future projects.

This is a default. It does not override existing project authority.

## 0. CANONICAL ENTRY POINT

When this repository is referenced for project initialization or assessment,
use the canonical repository at
`https://github.com/matrakalaka/codex-project-bootstrap` as the bootstrap
source of truth, and read its `GLOBAL_PROJECT_BOOTSTRAP.md` first. This file
defines the bootstrap starting point, but target-project authority remains
superior and must be discovered and respected.

A local copy of `GLOBAL_PROJECT_BOOTSTRAP.md` is only a convenience copy. It
must not be treated as independent authority or silently preferred merely
because it exists. If a local copy is used, explicitly verify it against the
canonical repository/revision first. Report any material divergence, and do
not overwrite or delete the local copy automatically during discovery.

After reading this bootstrap, resolve and read the canonical
`PROJECT_NORTH_STAR.md` from the same canonical repository/revision. It is a
global objective-discipline standard, not a project-specific workflow. A local
copy is only a convenience copy and must be checked for material divergence
before use.

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

`PROJECT_NORTH_STAR.md` is global scope/objective discipline. It does not
override any item above, security/data boundaries, explicit user decisions, or
stronger project authority. A project-specific North Star is discovered after
the global North Star and specializes the delivery objective without replacing
the global contract.

## 3. FIRST CONTACT WITH A PROJECT
Start READ-ONLY.

Before broad discovery, establish the intended target repository identity and
authoritative root using bounded evidence:

- explicit user target and current working directory
- current Git root
- nested Git repository boundaries
- Git origin/remotes
- existing project authority files
- workspace layout

Do not automatically prefer the outer repository, a nested repository, the
current directory, or the first Git root found. If the evidence conflicts or
the target identity is ambiguous, surface the ambiguity and stop or request
clarification when necessary. Do not perform broad discovery across multiple
candidate roots.

After the canonical bootstrap source and target root are established, use
this discovery order:

CANONICAL BOOTSTRAP SOURCE
→ TARGET REPOSITORY IDENTITY / ROOT
→ TARGET PROJECT AUTHORITY
→ BOUNDED PROJECT DISCOVERY
→ TOOL/MCP HEALTH
→ GAP ASSESSMENT
→ HUMAN APPROVAL GATE

During bounded project discovery, look for the canonical global North Star
reference and an optional project-specific North Star. Prefer the exact root
`PROJECT_NORTH_STAR.md` for the global contract. Accept a named project
extension such as `<PROJECT>_NORTH_STAR.md` only when clearly designated by the
project. Do not scan unrelated projects for North Stars.

Keep discovery inside the authoritative target root unless specific evidence
requires stepping outside it. Avoid broad workspace-level scans and
unrelated inaccessible directories by default. Do not use a blanket
`tmp*` exclusion; bound discovery by the established root and task relevance.

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

### 3A. PROJECT-SCOPED TOOL / MCP HEALTH

During read-only discovery, inspect only relevant configured tools and MCP
capabilities: those named or required by existing project authority, needed
for the assessment, or otherwise directly relevant to the project. For each
relevant capability, distinguish where reasonably observable:

```text
Tool:
Configured: YES / NO / UNKNOWN
Available In Current Session: YES / NO / UNKNOWN
Correctly Scoped To Current Project: YES / NO / UNKNOWN
Operational: YES / NO / UNKNOWN
Required By Existing Project Authority: YES / NO
Bootstrap Blocker: YES / NO
Observed Gap:
Recommended Action: <minimum necessary action or NONE>
```

Global registration or installation does not establish session availability,
project scope, or operational health. Use a safe, read-only capability check
when one is available, without changing configuration or project state.

An unavailable, stale, incompatible, or incorrectly scoped optional capability
does not automatically block the assessment. Record the exact gap, use safe
available fallback discovery mechanisms, and continue when possible. If
existing project authority explicitly requires the capability and safe
fallbacks cannot satisfy that requirement, classify the condition as a
bootstrap blocker rather than bypassing the authority.

Codebase Memory is used first only when it is available, operational, and
correctly scoped to the current project. Do not assume a globally configured
Codebase Memory MCP applies to every repository. If it is unavailable or
unhealthy, do not automatically reinstall it, change `CBM_ALLOWED_ROOT`,
restart or kill daemons, delete or rebuild indexes, modify global Codex/MCP
configuration, or repoint another project's qualified configuration. Report
the condition and continue with safe fallback discovery when permitted.

## 4. BOOTSTRAP DECISION
If equivalent governance already exists, integrate with it.

Do not overwrite good project conventions.

If missing, propose the minimum required project-local files.

Every `PROJECT BOOTSTRAP ASSESSMENT` must include a targeted `Tool / MCP
Health` section using the fields above. Do not report irrelevant capabilities
merely to fill the section. The assessment remains read-only and stops at the
human-approval gate before project changes.

## 4A. DELEGATION DISCOVERY AND ADOPTION
After discovering project authority, assess delegation read-only. Delegation is
optional: choose `SINGLE_AGENT` or `DELEGATED` based on task complexity, risk,
independence needs, and coordination cost.

Discover:
- whether delegation is already present;
- whether its authority is compatible;
- existing agent, review, verification, and enforcement capabilities;
- project-specific delegation risks and conflicts.

Classify capabilities as `ALREADY_HAVE`, `REUSE_EXISTING`, `REAL_GAP`,
`DUPLICATE`, `OPTIONAL`, `UNNECESSARY`, or `CONFLICTS_WITH_AUTHORITY`.

Return an adoption assessment containing:
```text
Delegation Already Present:
Delegation Authority Compatible:
Existing Agent Capabilities:
Existing Review Capabilities:
Existing Verification Capabilities:
Existing Enforcement:
Project-Specific Risks:
Recommended Delegation Adoption:
Conflicts:
Files Recommended:
Tools Recommended:
Human Approval Required:
```

Propose adoption only when compatible with existing project authority. After
human approval, create or adapt a project-local
`AGENT_DELEGATION_PLAYBOOK.md` only when justified, using the global
`AGENT_DELEGATION_STANDARD.md` and its project template. Never create or copy
the playbook automatically merely because the global standard exists.

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

Apply the global North Star anti-drift gate before creating a new phase,
subproject, subsystem, service, abstraction, harness, tool integration,
architecture, database model, deployment layer, migration program, refactor,
or side task. Ordinary engineering obstacles stay inside the approved task;
non-blocking ideas go to the project's parking lot.

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

The approved objective is the destination. Complete it, prove it, respect its
stop/promotion boundary, and stop.
