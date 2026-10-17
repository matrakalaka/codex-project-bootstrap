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
| Open Terminal | **BLOCKED** — exact provider/repository was not supplied | Unknown: macOS application, host helper, or MCP | None; no similarly named substitute | `BLOCKED` with source-identity error |
| MiroFish | `https://github.com/666ghj/MiroFish` at `v0.1.2` | Python/Node application with local services | Manifest only; no MCP claim | `NOT_INSTALLED` |
| loadersz-core | `https://github.com/lumberjacque/loadersz-core` at `v0.9.0`; npm package `loadersz` | Browser Web Component/library | Manifest only; no MCP claim | `NOT_INSTALLED` |
| api-anything | `https://github.com/goodnight000/api-anything` at commit `b20d809d218a1273c1941b72a8cd8188e11da7cc` | Node CLI, MCP server, and upstream skill | `tooling/mcp.registration.json` | `NOT_INSTALLED` unless the CLI is present |

The registry intentionally reports optional tools as `NOT_INSTALLED` rather
than hiding them. `api-anything` becomes `AVAILABLE` only after its executable
passes the version/help checks. The manifest does not install packages,
create credentials, launch services, or modify global Codex configuration.

The Open Terminal row remains blocked until the owner supplies the exact
upstream identity. `Terminal.app` presence alone is not proof of the requested
integration.
