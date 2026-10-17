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

### Open Terminal — BLOCKED

The request did not identify an upstream repository, provider, or exact MCP
server. Bootstrap therefore does not substitute a similarly named terminal
MCP project and does not pretend that the installed macOS `Terminal.app` is
the requested integration. Supply the exact source before implementation.

### MiroFish — NOT_INSTALLED

The verified upstream is `https://github.com/666ghj/MiroFish`, pinned for this
registry to `v0.1.2`. Upstream documents a source deployment requiring Node
18+, Python 3.11–3.12, `uv`, configured API keys, and its own frontend/backend
services. Bootstrap records it as an application, not an MCP server. Install
and run it only in a separately approved project/application scope.

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
