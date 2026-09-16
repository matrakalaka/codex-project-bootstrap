# GLOBAL AGENT DELEGATION STANDARD

## PURPOSE

Provide a reusable, capability-based contract for safe, optional delegation
within Codex projects. This standard describes delegation behavior; it does
not install an agent framework or grant project permissions.

## AUTHORITY AND ACCOUNTABILITY

Existing project authority remains superior wherever applicable, including
`AGENTS.md`, nested authority, architecture, workflow, security, deployment,
testing, and known-good contracts. This standard and any project playbook are
subordinate operational guidance and cannot expand authority.

The parent/controller remains accountable for the task. A worker's `PASS`
never automatically becomes the parent task's `PASS`.

## DELEGATION DECISION

Choose explicitly between `SINGLE_AGENT` and `DELEGATED`.

Use `DELEGATED` when it materially improves parallel investigation,
specialist analysis, implementation isolation, independent review,
verification, UI review, security/data review, or evidence collection. Prefer
`SINGLE_AGENT` for simple, tightly coupled, or low-risk work where coordination
cost outweighs the benefit.

Delegation is optional for every task.

## CONTROLLER RESPONSIBILITIES

The controller must discover authority and repository reality, choose the
execution mode, define bounded packets, review and reconcile worker evidence,
inspect final worktree state, coordinate independent verification when
appropriate, determine the parent outcome, and authorize handoff only after
acceptance.

## STANDARD ROLES

Roles are capability-based and may be omitted when unnecessary:

- **Explorer:** read-only authority, structure, behavior, dependencies, and risk discovery.
- **Designer:** read-only seams, interfaces, risks, and verification proposal.
- **Implementer:** bounded changes within the assigned scope.
- **Test/Verifier:** authoritative tests, builds, checks, and runtime qualification.
- **UI Verifier:** objective UI, interaction, viewport, and accessibility verification.
- **Security/Data Auditor:** security, data, authorization, and environment-boundary review.
- **Reviewer:** independent scope, authority, diff, evidence, and regression review.
- **Handoff Recorder:** records the accepted checkpoint in the canonical project handoff.

## BOUNDED DELEGATION PACKET

Every delegated task should declare:

```text
Task ID:
Parent Task:
Role:
Objective:
Authority To Read:
Allowed Paths:
Allowed Files:
Protected Paths:
Read Permission:
Write Permission:
Command Permission:
Network Permission:
Database Permission:
Production Permission:
Deployment Permission:
External-Service Permission:
Git/GitHub Write Permission:
Commit Permission:
Push Permission:
Required Tests:
Required Evidence:
Known-Good Contracts:
Dirty Work To Preserve:
Stop Conditions:
Escalation Conditions:
Expected Outcome Format:
```

Undeclared privilege is not authorized. Packets cannot silently expand scope,
authority, environment, or permissions.

## WORKER EVIDENCE CONTRACT

Workers return bounded evidence using:

```text
Task ID:
Role:
Outcome:
Authority Read:
Files Inspected:
Files Changed:
Commands Executed:
Tests Executed:
Build Result:
Runtime Result:
UI Result:
Security/Data Result:
Evidence:
Known-Good Contracts Checked:
Scope Deviations:
Dirty Work Preserved:
Unexpected Findings:
Remaining Risks:
Recommended Next Action:
```

Missing or contradictory evidence prevents parent acceptance.

## OUTCOMES

Use the standard outcomes:

- `PASS` — completed and validated.
- `BLOCKED_PRECONDITION` — a required authority, access, capability, approval, or safe boundary is unavailable.
- `FAILED_AFTER_EXECUTION` — approved execution occurred but validation failed.
- `DIVERGENCE` — a protected boundary, wrong target, or approved-plan boundary was crossed.

If project authority defines conflicting terminology, that authority controls;
the project playbook records the adaptation.

## SAFETY AND STOP RULES

Before work begins, discover repository identity, origin, branch/ref, HEAD,
tracked modifications, staged modifications, and untracked files. Preserve all
pre-existing work unless explicitly assigned. Do not normalize repositories
destructively.

Stop and escalate when authority, environment identity, scope, permissions,
credentials, protected boundaries, or required verification cannot be
satisfied. Do not improvise around failed preconditions.

Recursive delegation is prohibited by default. Nested delegation requires
explicit parent-packet authorization and project-authority compatibility.

Preserve `one task  one session  one verified checkpoint`.

Handoff is written only after parent acceptance.

## EXTERNAL TOOLBOX AND CAPABILITY DISCOVERY

Integrate with `GLOBAL_PROJECT_RESOURCE_TOOLBOX_POLICY.md`. External
repositories, skills, MCPs, frameworks, and utilities are optional toolbox
resources, not authority or dependencies merely because they are available.

Use:

`DISCOVER  CLASSIFY  REUSE  IDENTIFY GAP  PROPOSE  APPROVE  QUALIFY  USE`

Classify capabilities as `ALREADY_HAVE`, `REUSE_EXISTING`, `REAL_GAP`,
`DUPLICATE`, `OPTIONAL`, `UNNECESSARY`, or `CONFLICTS_WITH_AUTHORITY`.

No specific tool, database, MCP, framework, browser, container, memory index,
or enforcement product is globally mandatory. Reuse project-authorized
capabilities where available.

## VERIFICATION

Use independent verification when risk, project authority, or task
characteristics justify it. Do not create artificial independence where it
adds no meaningful assurance. The controller performs final reconciliation and
parent outcome classification.
