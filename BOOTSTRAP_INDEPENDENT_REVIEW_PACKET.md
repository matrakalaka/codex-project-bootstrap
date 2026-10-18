# Bootstrap Independent Review Packet

Review status: **PENDING independent approval**. This packet records evidence
for a reviewer; it is not a self-issued approval.

## Scope reviewed

The review target is branch `release-candidate/agentterm-bootstrap-20261018`,
with final local commit `5633e59` (preceded by launcher commit `9fb5f5f`),
based on `be9b844bfdaa89f4c695583726b72121a2621e95`, including the AgentTerm
facade, vendored source boundary, launcher installer, tool discovery, host
bridge, and synthetic lifecycle tests.

## Control findings

| Control | Finding | Evidence / residual risk |
| --- | --- | --- |
| Authority precedence | PASS | Launcher resolves authority before Codex or AgentTerm; lifecycle requires verified revision and file hashes. |
| Approval before edits | PASS | Default launcher is read-only; AgentTerm execution requires a persisted matching plan and interactive confirmation. |
| Session isolation | PASS | Session state binds project root and normalized Git identity; cross-project opens are rejected. Repeated initialization returns the existing matching session rather than creating a duplicate. |
| Ledger integrity | PASS | Resume/status verify the hash chain; tamper fixture is rejected. A hash chain is evidence, not a complete security boundary. |
| Task correlation | PASS | Plan task/correlation IDs are passed into the AgentTerm runner and persisted in session state/ledger. |
| Git scope and HEAD drift | PASS | Plan captures expected HEAD/scope; execution rejects drift or mismatched scope. |
| Independent verification | PASS/PENDING review | Verification records and scope checks are implemented; reviewer must inspect that the verifier is independent of the executing agent in deployment use. |
| Host bridge / Open Terminal | PASS with explicit limits | Managed PTY is allowlisted by session identity, approval-gated, bounded, audited, and captures output/status. Native Terminal.app supports new-tab launch only; arbitrary existing-tab attach and native output capture are unsupported. |
| Failure recovery | PASS | Denied authorization, missing AgentTerm, invalid authority, corrupted ledger, and interrupted/changed-head paths produce blocked outcomes. |
| Cross-project contamination | PASS | Synthetic project identity mismatch is rejected. |
| Backward compatibility | PASS | Existing Bootstrap tests and launcher installer tests remain in the suite. |
| External activation | PENDING | Active `~/.zshrc`, global MCP registration, GitHub publication, and independent approval were intentionally not changed. |

## Open Terminal evidence

`Terminal.app` and `osascript` were present. A harmless native command was
launched in a new Terminal.app tab and returned window identifier `9523`.
Managed PTY synthetic tests passed for approval denial, multiline input,
output/exit capture, session selection, close, cleanup, and AgentTerm ledger
events. This does not establish control over arbitrary preexisting tabs or an
already-running Codex process.

## Defect found and corrected during review

The first direct pass found that repeated `initialize()` calls overwrote the
session projection and appended a second session-start event. This violated
the duplicate-session invariant. The lifecycle now loads an existing session,
requires matching project identity and authority revision/files, and returns
the existing state; mismatches fail closed. The regression is covered by
`test_complete_lifecycle_and_fresh_resume`.

Focused result: **7 AgentTerm Bootstrap lifecycle tests passed**. Full result:
**54 Bootstrap tests passed and 87 AgentTerm tests passed**.

## Reviewer actions

An independent reviewer should inspect the diff from the AgentTerm-core
baseline, run the documented test commands, review the generated synthetic
evidence, and explicitly approve or reject the candidate. No approval is
inferred from prior implementation reports.

## Protected-boundary statement

Review and qualification used synthetic repositories and harmless fixtures.
There were no ADB commands, Android connections, port 15041 changes, or
UltimateBoxManager modifications.
