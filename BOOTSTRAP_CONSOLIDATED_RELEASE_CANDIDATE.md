# Bootstrap Consolidated Release Candidate

Status: **PARTIAL — ready for independent review; not published or activated in the owner shell**.

## Baseline and ancestry

This release candidate is branch `release-candidate/agentterm-bootstrap-20261018`,
final local commit `5633e59`, based on the verified AgentTerm-core commit
`be9b844bfdaa89f4c695583726b72121a2621e95`. Its ancestry includes the four-tool
work (`8254316`, `dced2c2`, `f3c3ea4`, `475e747`) and AgentTerm source work
(`43e35b5`, `274dd7d`). Existing `main` and all prior worktrees were preserved.

## Consolidated architecture

Bootstrap remains authoritative for project authority resolution, lifecycle
boundaries, and publication policy. `scripts/agentterm_bootstrap.py` is the
first-class lifecycle facade: it creates project-scoped sessions, records
Bootstrap authority and task correlation in AgentTerm's ledger, requires a
persisted plan before execution, delegates bounded host operations to the
existing bridge, and validates continuity on resume.

The canonical launcher remains read-only by default. Its explicit
`--agentterm --approve-agentterm-init` mode performs read-only discovery first,
then initializes the lifecycle only after the second, explicit authorization.
It fails closed when the published checkout lacks `bootstrap_session.py`.

No global Codex MCP configuration, active `~/.zshrc`, GitHub `main`, production
service, UltimateBoxManager checkout, ADB daemon, or device was changed.

## Integrated inventory

| Capability | Candidate result | Evidence |
| --- | --- | --- |
| AgentTerm lifecycle | AVAILABLE in isolated provisioning | `bootstrap_session.py`, ledger/session tests, isolated `--version`/`--help` health check |
| loadersz-core | AVAILABLE in isolated provisioning | pinned checkout/package and discovery result |
| MiroFish | INCOMPATIBLE | isolated `uv`/Python 3.11 provisioned; dependency sync is blocked by pinned `torch==2.9.1` lacking a macOS x86_64 wheel |
| api-anything | NOT_REGISTERED | isolated CLI passes health checks; active Codex config intentionally unchanged |
| Open Terminal | AVAILABLE with explicit limits | Bootstrap-governed managed PTY and native Terminal.app new-tab launch; arbitrary existing-tab attachment and native output capture are unsupported |

The local manifest and discovery matrix retain these states explicitly; no
optional tool is silently omitted.

## Release boundary

The candidate is locally implemented and testable, but independent review,
owner approval for the shell installation, and publication authorization remain
required before it can become the owner's active launcher.
