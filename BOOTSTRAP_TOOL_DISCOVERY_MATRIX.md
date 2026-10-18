# Bootstrap Tool Discovery Matrix

This registry is authoritative for the optional integrations requested for
Bootstrap. Discovery is read-only and never treats a name in documentation as
an installed or operational tool.

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/tool_discovery.py --json
```

| Tool | Upstream | Actual interface | Bootstrap registration | Fresh-session result |
| --- | --- | --- | --- | --- |
| AgentTerm | **Owner-supplied local archive**; SHA-256 `17b6784fe8a96e7667719131209fc44ecefd56010f69479ac1b6124690e5d500` | Python governed CLI, memory ledger, approval/scope runner, Codex adapter | `tooling/agentterm.integration.json`; isolated package source under `vendor/agentterm` | `AVAILABLE` when `.bootstrap-tools/install/agentterm-venv/bin/agentterm` passes `--version`/`--help` |
| Open Terminal | Bootstrap-governed native capability; no external provider substituted | Managed PTY plus native Terminal.app new-tab launch via `osascript` | `scripts/open_terminal_bridge.py`; AgentTerm ledger integration | `AVAILABLE`; arbitrary existing-tab attach and native output capture remain unsupported |
| MiroFish | `https://github.com/666ghj/MiroFish` at `v0.1.2` | Python/Node application with local services | Manifest only; no MCP claim | `INCOMPATIBLE` on this macOS x86_64 host: isolated `uv`/Python 3.11 provisioned, but the lock pins `torch==2.9.1` without an x86_64 macOS wheel |
| loadersz-core | `https://github.com/lumberjacque/loadersz-core` at `v0.9.0`; npm package `loadersz` | Browser Web Component/library | Manifest only; no MCP claim | `NOT_INSTALLED` |
| api-anything | `https://github.com/goodnight000/api-anything` at commit `b20d809d218a1273c1941b72a8cd8188e11da7cc` | Node CLI, MCP server, and upstream skill | `tooling/mcp.registration.json` | `NOT_INSTALLED` unless the CLI is present |

The registry intentionally reports optional tools as `NOT_INSTALLED` rather
than hiding them. `api-anything` becomes `AVAILABLE` only after its executable
passes the version/help checks. The manifest does not install packages,
create credentials, launch services, or modify global Codex configuration.

Open Terminal is implemented as a Bootstrap capability rather than an invented
third-party provider. Native mode launches a new Terminal.app tab through
`osascript`; managed mode provides deterministic PTY input/output and is the
recommended execution path. Bootstrap does not send input to whichever tab is
active and does not claim output capture from arbitrary existing tabs.

An isolated provisioning root can be inspected with `--tool-root`; this does
not make a tool globally installed or active in Codex. An installed MCP CLI is
reported `NOT_REGISTERED` until the active Codex configuration contains the
validated server entry. The 2026-10-18
qualification is recorded in `BOOTSTRAP_FOUR_TOOL_INTEGRATION.md`.

Current isolated qualification: MiroFish `INCOMPATIBLE` after an actual
isolated dependency-sync attempt, loadersz-core `AVAILABLE` as an isolated
library, and api-anything `NOT_REGISTERED` despite an operational isolated
CLI. The latter is intentionally not reported as active until Codex
configuration approval is granted.
