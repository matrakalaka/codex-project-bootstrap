# Final Independent Human Review Request

Review target: `release-candidate/agentterm-bootstrap-20261018`

Candidate commit:

```text
b51838370d9735a0cafa5d5ffbaf0203f61a9b8b
```

Remote baseline observed: `origin/main` at
`ed9254976fa72c8b8c11bb8e060349630bf981d6`. The candidate is a descendant of
that remote baseline. The local `main` checkout remains dirty and was not used
for publication.

## Review scope

Please independently inspect the candidate diff and verify:

- authority resolution remains before AgentTerm initialization;
- project identity, authority revision, and session state are bound together;
- repeated initialization cannot create duplicate sessions;
- approval, plan, HEAD drift, scope, and ledger checks fail closed;
- host execution and managed PTY operations are bounded and audited;
- native Terminal.app is limited to approved new-tab launch;
- arbitrary existing-window/Codex attachment is not claimed;
- default `codex-bootstrap` remains read-only;
- launcher activation remains publication- and approval-gated;
- existing MCP registrations and protected systems remain untouched.

## Evidence available

- Bootstrap suite: **56 passed**.
- AgentTerm suite: **87 passed**.
- Managed PTY multiline/output/status tests: passed.
- Managed `codex --version` smoke: `codex-cli 0.163.0`, exit 0.
- Native Terminal.app smoke: new-tab launch returned window identifier `9523`.
- Shell syntax, Python compilation, diff checks, and tool discovery: passed.
- Discovery: AgentTerm `AVAILABLE`, Open Terminal `AVAILABLE`, loadersz-core
  `AVAILABLE`, MiroFish `INCOMPATIBLE`, api-anything `NOT_REGISTERED`.

## Known limitations and risks

- Native Terminal.app output capture and arbitrary preexisting-tab attachment
  are unsupported and fail closed.
- MiroFish remains incompatible on this macOS x86_64 host because its pinned
  `torch==2.9.1` lacks a compatible wheel.
- api-anything global MCP registration has not been applied.
- The live shell launcher has not been changed.
- GitHub `main` has not been changed.

## Required review response

Record one of:

```text
APPROVED: b51838370d9735a0cafa5d5ffbaf0203f61a9b8b
```

or:

```text
REJECTED: <specific finding and required correction>
```

Approval must come from an authorized independent human reviewer. A Codex
self-review or prior implementation report does not satisfy this gate.
