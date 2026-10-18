# Bootstrap Independent Review Packet

Review status: **PENDING independent approval**. This packet records the
remediation evidence for a reviewer; it is not a self-issued approval.

## Scope reviewed

The review target is branch `release-candidate/agentterm-bootstrap-20261018`,
at the local remediation candidate commit, based on the AgentTerm-core
integration and including the AgentTerm facade, vendored source boundary,
launcher installer, tool discovery, host bridge, and synthetic
lifecycle/security tests.

## Control findings

| Control | Finding | Evidence / residual risk |
| --- | --- | --- |
| Authority precedence | PASS | Launcher resolves authority before Codex or AgentTerm; lifecycle requires verified revision and file hashes. |
| Approval before edits | PASS | Default launcher is read-only; AgentTerm execution requires a persisted matching plan and interactive confirmation. |
| Session isolation | PASS with managed-host qualification pending | Session state binds project root and normalized Git identity; concurrent and interrupted initialization are locked/idempotent; terminal capabilities and metadata are session/project-bound. |
| Ledger integrity | PASS with documented limits | Status, resume, and verify block on corruption; tamper fixture is rejected. A hash chain is evidence, not a complete filesystem security boundary. |
| Task correlation | PASS | Plan task/correlation IDs are passed into the AgentTerm runner and persisted in session state/ledger. |
| Git scope and HEAD drift | PASS | Plan captures expected HEAD/scope; execution rejects drift or mismatched scope. |
| Independent verification | PASS/PENDING review | Verification records and scope checks are implemented; reviewer must inspect that the verifier is independent of the executing agent in deployment use. |
| Host bridge / Open Terminal | PASS with managed-host evidence pending | Managed PTY now authenticates socket requests, rejects replay, terminates its process group on timeout, and preserves close failure states. Four managed integration tests are unverified because this sandbox denies AF_UNIX bind. Native Terminal.app supports new-tab launch only; arbitrary existing-tab attach and native output capture are unsupported. |
| Failure recovery | PASS | Denied authorization, missing AgentTerm, invalid authority, corrupted ledger, and interrupted/changed-head paths produce blocked outcomes. |
| Cross-project contamination | PASS | Synthetic project identity mismatch is rejected. |
| Backward compatibility | PASS | Existing Bootstrap tests and launcher installer tests remain in the suite. |
| External activation | PENDING | Active `~/.zshrc`, global MCP registration, GitHub publication, and independent approval were intentionally not changed. |

## Open Terminal evidence

`Terminal.app` and `osascript` were present. A harmless native command was
launched in a new Terminal.app tab and returned window identifier `9523`.
Managed PTY security/unit tests passed for capability authorization, replay,
cross-project binding, metadata integrity, process-group termination, and
failed close. Managed socket integration tests were explicitly skipped because
AF_UNIX bind returns `EPERM` in this sandbox. This does not establish control
over arbitrary preexisting tabs or an already-running Codex process.

## Defect found and corrected during review

The first direct pass found that repeated `initialize()` calls overwrote the
session projection and appended a second session-start event. This violated
the duplicate-session invariant. The lifecycle now loads an existing session,
requires matching project identity and authority revision/files, and returns
the existing state; mismatches fail closed. The regression is covered by
`test_complete_lifecycle_and_fresh_resume`.

Focused result: **68 Bootstrap/security tests, 64 passed and 4 skipped**.
The vendored AgentTerm pytest suite is **NOT RUN** because its isolated pytest
environment was absent and network access was unavailable; no pass claim is
made.

## Remediation review actions

The prior seven findings are addressed in
`BOOTSTRAP_SECURITY_REMEDIATION_20261018.md`. The reviewer must inspect the
capability protocol, process-group cancellation, initialization lock/recovery,
verification authorization policy, status exit behavior, metadata MAC, and
close-state transitions, then rerun the available tests. Four managed PTY
integration tests are explicitly unverified in this sandbox because AF_UNIX
bind returns `EPERM`; they must be rerun on an approved host before claiming
host-qualified managed PTY evidence.

## Reviewer actions

An independent reviewer should inspect the diff from the AgentTerm-core
baseline, run the documented test commands, review the generated synthetic
evidence, and explicitly approve or reject the candidate. No approval is
inferred from prior implementation reports.

## Protected-boundary statement

Review and qualification used synthetic repositories and harmless fixtures.
There were no ADB commands, Android connections, port 15041 changes, or
UltimateBoxManager modifications.
