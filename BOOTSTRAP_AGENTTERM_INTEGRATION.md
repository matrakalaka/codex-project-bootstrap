# Bootstrap AgentTerm Integration

Status: `AVAILABLE` as an isolated local Bootstrap capability; `PARTIAL` for
the Open Terminal request.

## Source and provenance

The owner-supplied archive was found at `/Users/admin/codex-project-bootstrap/agentterm.zip`.
It is a non-encrypted ZIP with 62 entries, no absolute or parent-traversal
paths, and `unzip -t` reported no errors. SHA-256:

```text
17b6784fe8a96e7667719131209fc44ecefd56010f69479ac1b6124690e5d500
```

The archive does not identify an upstream repository. Bootstrap therefore
records it as an owner-supplied local source and does not invent an upstream
identity. The reviewed source is preserved under `vendor/agentterm/` and is
pinned by the archive hash in `tooling/bootstrap_tools.json` and
`tooling/agentterm.integration.json`.

The package is `agentterm` version `0.1.0`, Python `>=3.11`, with no runtime
dependencies. `pytest` is a development-only dependency. Installation is
isolated at `.bootstrap-tools/install/agentterm-venv`; no global or privileged
installation is required.

## What was reused

AgentTerm contains the same Bootstrap contracts and playbook concepts already
present in this repository: task, approval, result and assessment packets;
North Star and checkpoint handling; append-only hash-chained SQLite memory;
Git-observed scope enforcement; outcome classification; redaction; and
Codex/Claude/generic CLI adapters. The package test suite contains the
reconstructed `tests/test_runner.py`, `pyproject.toml`, and package
`.gitignore`; they were not overwritten in the Bootstrap checkout.

Bootstrap retains its own host bridge and discovery implementation as the
canonical integration boundary. AgentTerm does not replace or broaden that
bridge.

## Codex compatibility

The installed Codex is `codex-cli 0.163.0`. AgentTerm's Codex adapter invokes:

```text
codex exec --sandbox <read-only|workspace-write> --cd <repo> -
```

`agentterm doctor` reported the adapter available, version `codex-cli
0.163.0`, and no missing required flags (`--sandbox`, `--cd`). The adapter
does not claim that `--dangerously-bypass-approvals-and-sandbox` or YOLO mode
is safe or required.

## Open Terminal finding

AgentTerm is not the native macOS Terminal application, does not launch
`Terminal.app`, and does not identify an external Open Terminal provider. It
cannot satisfy that request by name substitution. The Open Terminal capability
remains `BLOCKED` until its exact provider or upstream source is supplied.

AgentTerm can run an agent CLI from a terminal and can use the Bootstrap
host-execution bridge for explicitly approved synthetic/host operations. That
is a different capability and is not reported as native Terminal integration.

## Safety and coverage

The reviewed package uses bounded subprocess calls for Git, declared agent
commands, verification commands, and manifest checks. Its installer executes
commands declared by a repository manifest after the AgentTerm approval gate;
Bootstrap does not invoke that installer automatically and treats manifests as
untrusted until reviewed. It has no network client or MCP server. Scope
violations are classified from Git-observed changes;
approval is bound to repository identity and HEAD; memory writes are
hash-chained and redacted. The package's test suite includes ledger tamper
detection, scope collisions, approvals, command execution, checkpoint
isolation, and CLI end-to-end fixtures.

The reported overwrite evidence is limited to the archive itself: those three
paths exist inside the owner-supplied archive. Bootstrap Git history has no
`test_runner.py` or `pyproject.toml` path history; the only relevant history
is the prior root `.gitignore` addition and the provisioning checkpoint's
`.gitignore` edit. No existing Bootstrap file was overwritten during this
integration.
