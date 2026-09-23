# Global Engineering Standard

Status: NORMATIVE

This standard is inherited by projects initialized through
`GLOBAL_PROJECT_BOOTSTRAP.md`. It defines technology-independent engineering
invariants. Project and subsystem authorities own exact implementation details
and may impose stricter rules; they must not weaken this standard silently.

## Authority and evidence

Before governed work, read the applicable global bootstrap, project authority,
subsystem contracts, known-good evidence, testing/security/deployment
authority, and relevant Codebase Memory. Resolve authority in this order:

1. explicit task scope and safety authorization;
2. this global standard;
3. project authority;
4. subsystem and operation-specific contracts;
5. current source and tests as implementation/evidence;
6. historical records and task handoffs as immutable evidence;
7. external tools as non-authoritative toolbox inputs.

More-specific authority owns exact details and may be stricter. Conflicts are
not resolved silently: preserve evidence, stop, and report the conflict.
Normative contracts must be recoverable from repository authority, not chat
memory. After restart or compaction, reread the applicable authority before
continuing.

Evidence claims must state their scope. For example: `UNIT-QUALIFIED`,
`INTEGRATION-QUALIFIED`, `HOST-QUALIFIED`, `ENVIRONMENT-PROVEN`,
`DEPLOYMENT-PROVEN`, or `FLEET-PROVEN`. A narrower level never implies a
broader one.

## Defect resolution standard

The canonical workflow is:

```text
OBSERVE → AUTHORITY READ → KNOWN-GOOD SEARCH → CLASSIFY → ROOT CAUSE
→ OWNING LAYER → BOUNDARY → DIAGNOSE → AUTHORIZE → IMPLEMENT
→ RECURRENCE PROOF → APPLICABLE COMPATIBILITY MATRIX → FULL REGRESSION
→ DOCUMENT
```

The permanent shorthand is:

```text
ROOT CAUSE → OWNING LAYER → COMPLETE FIX → RECURRENCE PROOF
→ APPLICABLE COMPATIBILITY MATRIX → FULL REGRESSION
```

`Symptom != root cause`; a failing line or test is not automatically the
owning layer or the defect. Establish `LAST PROVEN GOOD` and `FIRST PROVEN
BAD` where evidence permits. If evidence is insufficient, perform the
smallest safe diagnostic that can resolve the uncertainty.

A complete fix restores the violated invariant at its smallest correct owner
and audits affected consumers. It does not mean rewriting a subsystem. Do not
weaken expected behavior, hide errors, special-case an observed instance
without architectural justification, or reopen known-good behavior without
direct evidence.

## Observed instance is not architecture

An observed instance is evidence, not architecture.

A defect found in one environment is evidence of a potentially broader
contract defect until the owning layer establishes the actual scope.

Environment-specific facts may become regression fixtures; they must not
silently become environment-specific production architecture. Do not base
production behavior on one customer, machine, browser, database row, network,
repository state, deployment, IP address, serial number, or other observed
instance unless identity-specific behavior is an explicit product requirement.

Differences belong in validated capabilities, profiles, compatibility
contracts, configuration, or explicit product policy. Unknown environments
fail closed until qualified; similar-looking environments are not silently
assigned a known contract.

## Applicable compatibility

Each change MUST identify the compatibility dimensions relevant to its owning
contract, rather than testing every conceivable environment. Dimensions may
include operating systems, runtimes, architectures, browsers, schemas,
historical data, hardware, network conditions, authentication states,
concurrency, interruption/restart, deployment versions, artifacts, and
integrations. Test the applicable matrix and avoid irrelevant combinatorial
expansion.

## Canonical ownership and projections

Every important semantic fact MUST have one canonical owner. Caches, UIs,
reports, inventories, summaries, logs, and APIs are projections or evidence;
they must not become competing authorities. Consumers use the canonical
representation and must not choose whichever value allows execution to
continue. Projection disagreement is explicit drift, not permission to edit a
projection.

Cross-component and public APIs require stable semantic contracts. Meaning,
error, authentication, retry, and version changes require compatibility
evidence and an explicit migration/deprecation boundary.

## Fail-safe behavior and stop conditions

Where correctness, security, identity, authorization, data integrity,
destructive mutation, or ambiguous state is involved, uncertainty MUST NOT
silently become success, safety, authorization, presence, absence, or
support. In particular, do not coerce `UNKNOWN` into a known result.
`NOT_RUN` is never `PASS`.

Stop when authority conflicts, identity or capability mismatches, unsupported
schemas, artifact drift, ambiguous ownership, unexpected state, security
uncertainty, scope expansion, missing authorization, or indistinguishable
success/unknown is encountered. Preserve evidence, classify the condition,
report the blocker, and require the next smallest governed task. Do not
improvise.

Use the project outcome vocabulary where defined. At minimum preserve these
meanings when applicable: `PASS`, `BLOCKED_PRECONDITION`,
`FAILED_AFTER_EXECUTION`, and `DIVERGENCE`.

## Security and trust boundaries

Use least privilege, explicit trust boundaries, authenticated sensitive
operations, authorization distinct from reachability, replay protection where
relevant, isolation between security domains, and revocation/rotation where
required. A network connection is not trust. Failure must not broaden
privilege.

Secrets, credentials, tokens, private keys, authorization headers, and
equivalent material MUST remain in authorized secure stores and MUST NOT enter
logs, journals, URLs, artifacts, diagnostics, or error payloads. Exact
cryptographic and credential mechanisms remain project-specific.

## Destructive actions and ownership

Discovery, testing, planning, preview, and qualification are not mutation
authorization. Authorization MUST bind the concrete target, plan, scope,
preserved scope, artifacts, and required provenance. Material drift
invalidates authorization; there is no silent auto-replan or scope expansion.

Human authorization is a boundary, not a workflow engine. Once a goal and
required authority are established, the system SHOULD autonomously continue
through all safe, governed, already-authorized stages until verified
completion or a genuine new authority or decision boundary is reached.
Autonomous continuation applies only while the existing authority and
authorization envelope remains valid. Scope, target, identity, plan,
mechanism, security, or other materially bound drift may require a new
boundary. Verification remains part of completion wherever the governing
contract requires it; this principle does not weaken fail-closed behavior,
destructive consent, or human decision boundaries.

Mutation requires proven ownership of the resource: files, records, schemas,
cloud resources, processes, configurations, credentials, devices, or external
systems. Prefer typed, bounded, ownership-specific primitives over arbitrary
delete, reset, shell, migration, or infrastructure operations. Broad cleanup
is not a substitute for understanding ownership.

## State, operations, retry, and concurrency

Multi-step workflows with side effects MUST use explicit states, transitions,
checkpoints, reason codes, and operation/request IDs. Define initial,
intermediate, terminal, invalid, interruption, retry, resume, cancellation,
and uncertain-outcome behavior where relevant.

Terminal history is immutable. A failure is not rewritten into success or
retroactively made resumable. Completed mutation is not replayed unless the
owning contract proves idempotence. A retry requires bounded attempts,
explicit timeout/backoff semantics, duplicate handling, and uncertain-outcome
rules. Timeout or connection loss is not automatically success or failure.

Shared mutable state requires transactions, leases, locks, generation checks,
compare-and-swap, or an equivalent single-writer/conflict contract.
Process-local locks are not cross-process safety. Retention must preserve
operation-family lineage and diagnostic evidence.

Cancellation must match reality: request cancellation, execution stopped, and
outcome unknown are distinct unless the system can prove equivalence.

## Historical evidence and schema evolution

Historical failures, operations, receipts, logs, migrations, and qualification
results are immutable evidence. Use explicit compatibility readers or audited
migrations; do not rewrite history merely to fit current architecture.

Persisted and exchanged contracts need an owner and explicit schema/version
semantics. Compatibility must be narrow, deterministic, documented, and
tested. Missing fields, wrong types, contradictory aliases, incomplete data,
and unsupported versions fail closed. Producers and consumers evolve
deliberately; remove compatibility paths only after retained historical states
no longer need them.

## Artifacts, dependencies, and release identity

Governed artifacts require the provenance appropriate to the project:
authoritative source, exact version/build, hash, signature where supported,
compatibility, manifest, and reproducible build identity. Do not silently
substitute artifacts or use unpinned `latest` during governed execution.
Third-party repositories and tools are toolbox resources, not authority or
permission to install/adopt dependencies.

Do not assume checked-out source equals built, deployed, or running code.
Where relevant, verify source revision, build inputs, artifact fingerprints,
deployment, configuration, and runtime identity. Release qualification tests
the resulting artifact/tree and records the relevant evidence.

## Observability and data-loss prevention

Retain bounded, non-secret evidence sufficient to diagnose a failure at its
owner without repeatedly touching an external environment: IDs, timestamps,
state transitions, checkpoints, reason codes, provenance, configuration and
runtime identity, capability evidence, artifact identities, and safe raw
failure representations. Distinguish host/tool success from remote/runtime
success, transport failure, timeout, and absence.

When a change can remove or overwrite data, prove the owned boundary first.
Do not invent rollback without a reliable baseline. Surgical rollback is not
safe when overwritten state cannot be restored; broad reset is not justified
merely because surgical recovery is difficult.

## Qualification and regression

Where external or destructive effects exist, use the applicable ladder:

```text
HOST / FAKE QUALIFICATION
→ TARGETED READ-ONLY ENVIRONMENT QUALIFICATION
→ PLAN / PREVIEW
→ ADMISSION
→ EXPLICIT AUTHORIZATION
→ MUTATION
→ INDEPENDENT VERIFICATION
```

One environment proof is not universal proof. Protected or reference
environments remain protected unless explicitly authorized.

Recurrence proof requires, proportional to risk: the actual failure-shape
fixture; owning-layer invariant tests; negative, malformed, conflict, and
boundary cases; applicable compatibility cases; affected-consumer audit;
integration coverage; fail-closed coverage; and known-good regression. A test
that merely mirrors the repaired implementation is insufficient. Where
practical, show that the fixture fails against the defective behavior.

## Documentation and specialization

Contract-changing work MUST update the owning normative documentation and
relevant references. Temporary task notes are not automatically authority.
Tests should assert semantics, not fragile prose formatting. Superseded
authority is marked or removed according to project policy.

Projects MUST specialize this standard only where necessary. The specialization
may add stricter vocabulary, platform contracts, capability matrices, or
authorization rules, but MUST NOT weaken a global invariant. Project and
subsystem documents retain exact fields, commands, cryptography, timing,
platform behavior, and domain-specific workflows; they should reference this
standard instead of duplicating it.

## Future technology

For each new subsystem, establish as applicable: owner, authority, contracts,
capabilities, compatibility dimensions, state and persistence model, security
boundary, mutation boundary, failure semantics, evidence model, qualification,
and regression strategy. This keeps the standard valid as technologies change
without predicting every technology.

## Definition of done

A defect or governed change is fully qualified only when applicable items pass:

```text
Root Cause: PROVEN
Owning Layer: IDENTIFIED
Owning-Layer Fix: COMPLETE
Affected Consumers: AUDITED
Actual Failure Regression: PASS
Negative / Boundary Regression: PASS
Applicable Compatibility Matrix: PASS
Known-Good Contracts: PASS
Affected Integration: PASS
Full Current Project Regression: PASS
Required Build/Static Checks: PASS
Documentation: CURRENT
Evidence Scope: ACCURATELY STATED
Unauthorized Mutation: NONE
Required environment/deployment qualification: COMPLETE or NOT_YET_PROVEN
```

No required `NOT_RUN` item may be reported as `PASS`.

## Anti-overengineering rule

Choose the smallest correct owning-layer fix. Do not redesign unrelated
systems, add speculative abstractions or compatibility branches, create
migration machinery without a persisted-state need, test irrelevant matrix
dimensions, or turn local implementation details into global policy.
