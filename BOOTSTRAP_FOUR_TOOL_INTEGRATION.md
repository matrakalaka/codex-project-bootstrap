# Bootstrap Four-Tool Integration

## Integration contract

Bootstrap owns discovery, provenance, capability reporting, and safe
initialization instructions. It does not silently install optional tools,
create credentials, start external services, or grant host access.

The machine-readable registry is `tooling/bootstrap_tools.json`. The read-only
checker is `scripts/tool_discovery.py`. A fresh project can use the checker to
report `AVAILABLE`, `NOT_INSTALLED`, `NOT_REGISTERED`, `INCOMPATIBLE`, or
`BLOCKED` with evidence.

## Tool-specific behavior

### Open Terminal — AVAILABLE with explicit limits

No external provider was identified, so Bootstrap implements this as a native
capability: managed PTY sessions plus controlled new-tab launch through
macOS `Terminal.app`/`osascript`. It does not substitute a similarly named
third-party terminal MCP project. Arbitrary existing-tab attachment and native
output capture remain unsupported.

### MiroFish — INCOMPATIBLE in the qualified host

The verified upstream is `https://github.com/666ghj/MiroFish`, pinned for this
registry to `v0.1.2`. Upstream documents a source deployment requiring Node
18+, Python 3.11–3.12, `uv`, configured API keys, and its own frontend/backend
services. Bootstrap records it as an application, not an MCP server. An
isolated `uv 0.13.1` and Python 3.11.15 were provisioned, but the actual
backend sync fails on this macOS x86_64 host because the lock pins
`torch==2.9.1`, which has no compatible x86_64 macOS wheel. No API keys or
services were started.

### loadersz-core — NOT_INSTALLED

The verified repository is `https://github.com/lumberjacque/loadersz-core` and
the package is `loadersz`, pinned here to `v0.9.0`. It is a browser Web
Component/library. It has no Bootstrap MCP registration and should become a
project dependency only when a target project actually uses browser loaders.

### api-anything — NOT_INSTALLED / REGISTERED DECLARATIVELY

The verified repository is
`https://github.com/goodnight000/api-anything`, pinned to commit
`b20d809d218a1273c1941b72a8cd8188e11da7cc`. Upstream documents Node 22.13+,
the local CLI, and the MCP command `api-anything mcp`. The compatible MCP
entry is recorded in `tooling/mcp.registration.json`; it is not active until
the executable is installed and the host/session is restarted as required by
the Codex environment.

Upstream's supported installation sequence is:

```sh
git clone https://github.com/goodnight000/api-anything.git
cd api-anything
npm ci
npm install -g "$(npm pack --silent)"
api-anything --help
```

Do not use `npm install -g github:...` for this tool. Credentials and learned
site data remain outside Bootstrap.

## Verification boundary

Bootstrap tests validate provenance, manifest completeness, registration
syntax, and missing-tool reporting. They do not claim that an optional tool is
operational unless its local executable and safe health check pass.

## 2026-10-18 isolated qualification

Provisioning was performed under the ignored repository-local
`.bootstrap-tools/` root without global installation:

- MiroFish `v0.1.2` / commit `985f89f49acbb44ee14d9d680682c741a44eeebe`:
  source and frontend dependencies installed; frontend build passed. Isolated
  backend sync was attempted with `uv 0.13.1` and Python 3.11.15, then failed
  at the pinned `torch==2.9.1` macOS x86_64 wheel constraint. No API keys or
  services were started.
- loadersz-core `v0.9.0` / commit
  `aa2c2defc8cea0d343d9bfbab70aca01ebd322f2`: typecheck passed, 226 tests
  passed, Angular adapter generation passed, and package build passed.
- api-anything commit `b20d809d218a1273c1941b72a8cd8188e11da7cc`: Node
  25.8.1 satisfies the upstream Node >=22.13 requirement; build, CLI help,
  MCP EOF startup, and the full upstream suite (620/620) passed. The
  executable is provisioned but remains `NOT_REGISTERED` in the active Codex
  configuration until owner approval is given for the exact MCP change.

Use `scripts/tool_discovery.py --tool-root .bootstrap-tools --json` to report the isolated
qualification without changing PATH or global Codex configuration.

### Pending active Codex registration

After explicit owner approval, back up `~/.codex/config.toml` and add this
server entry while preserving every existing entry:

```toml
[mcp_servers.api-anything]
command = "/Users/admin/codex-bootstrap-four-tool/.bootstrap-tools/install/api-anything/node_modules/.bin/api-anything"
args = ["mcp"]
```

The exact change must be reviewed against the current file before application;
this task did not create a backup or modify that file. Restart Codex, run
`codex mcp list`, and rerun `scripts/tool_discovery.py --tool-root
.bootstrap-tools --json`. Only then may api-anything become `AVAILABLE`.
