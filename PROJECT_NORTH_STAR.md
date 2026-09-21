# GLOBAL PROJECT NORTH STAR

## Purpose

The approved objective is the destination.

Discovery, testing, security review, tools, implementation failures, new
ideas, and refactoring opportunities may change how the destination is
reached. They do not automatically change what the destination is.

This is a scope and objective-discipline standard. It does not override
security boundaries, data safety, project architecture, known-good contracts,
explicit user decisions, or stronger project authority.

## North Star contract

For each substantial task, keep these four statements available:

1. **Final intended objective** — what the project is actually trying to accomplish.
2. **Required proof** — the evidence that proves the objective works.
3. **Explicitly out of scope** — work intentionally excluded.
4. **Stop / promotion boundary** — where this task ends and what approval is required before the next boundary.

For production-oriented work, the first item may be called the production or
final intended objective. For other projects, use final intended objective.

## Anti-drift gate

Before creating a new phase, subproject, subsystem, service, abstraction,
test harness, tool integration, architecture, database model, deployment
layer, migration program, refactor, or side task, ask:

1. Does it directly unblock or materially improve delivery of the approved objective?
2. Is it required now rather than merely useful, interesting, cleaner, or potentially valuable?
3. Can the approved objective be completed safely without it?

If the objective can safely be completed without the additional work, park the
idea and continue the current objective.

## Ordinary engineering stays in the task

Compile errors, test failures, imports, dependency issues, UI regressions,
selector problems, browser errors, configuration mistakes, small integration
defects, and task-caused regressions are normally solved inside the current
task:

**diagnose → fix → focused test → regression → continue**

Do not create a new phase for each ordinary obstacle. Create another governed
phase only when the work is materially different or requires a genuine
authority, security, data, deployment, destructive-action, or approval
boundary.

## Parked ideas

Preserve useful non-blocking discoveries without allowing them to hijack the
current task:

```text
PARKED IDEA
Idea: <idea>
Why it may help: <reason>
Related subsystem: <area>
Urgency: <LOW / MEDIUM / HIGH>
Blocks current objective: NO
```

A parked idea becomes active only when the user selects it, project authority
requires it, or verified evidence proves it blocks the current objective.

## Verified plan changes

New evidence may change the plan when it proves the current plan is unsafe,
cannot work, conflicts with project authority, crosses a real destructive or
security/data boundary, or the user changes the objective.

Report the evidence, classify the smallest proven boundary using the existing
outcome vocabulary (`BLOCKED_PRECONDITION`, `FAILED_AFTER_EXECUTION`, or
`DIVERGENCE`), and recommend the smallest change needed to resume. Do not
silently broaden the task.

## Continuous drift check

At meaningful decisions, check:

```text
Does this advance the approved objective?
  YES → continue.
  NO  → is it required to unblock the objective?
          YES → continue within the current task.
          NO  → park the idea and return to the objective.
```

## Safety, tools, and testing

Anti-drift does not mean rushing or skipping necessary safety. Use the
necessary authority, security review, rollback planning, testing, and
environment controls without turning them into a different project.

Tools are a toolbox, not a reason to expand scope. Use a tool, framework,
dependency, service, or harness only when it materially helps the approved
objective and is allowed by project authority.

Testing proves the actual objective. Prefer the closest safe representation of
the real system: the real browser workflow for browser behavior, hosted
integration where safely authorized, focused automation for backend behavior,
and temporary harnesses only when the real system cannot safely provide the
required evidence.

## Completion

When the approved objective is implemented, verified, qualified according to
project authority, and checkpointed where required, stop. Report what changed,
what was verified, known limitations, parked ideas, and the promotion or next
step boundary. Do not continue improving adjacent systems merely because more
work is possible.

## Project-specific extensions

Projects may add a specialized North Star, such as
`AMG_STAGING_TO_PRODUCTION_NORTH_STAR.md`. A project-specific North Star
specializes this global contract; it does not replace or silently contradict
it. Project authority may add stricter safety, verification, or promotion
requirements.
