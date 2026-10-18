ONE TASK: evaluate and install the explicitly approved project tooling.

TOOL:
<name>

PURPOSE:
<why this project needs it>

Read project authority first.

Before installation:
- confirm it is not already available
- confirm official source/package
- prefer project-local installation
- inspect compatibility with existing stack
- protect unrelated package/lockfile changes
- identify generated artifacts
- define validation
- do not disable antivirus/security controls

Install only what is approved.

Do not install unrelated browsers, plugins, hooks, MCPs, or companion tools unless explicitly required.

After installation:
- verify version
- run a minimal smoke test
- run build if relevant
- confirm existing testing/tooling remains intact
- git-ignore generated artifacts where appropriate

For Bootstrap's optional integrations, run the read-only checker before and
after installation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/tool_discovery.py --json
```

For an isolated provisioning root, pass `--tool-root <path>` or set
`CODEX_BOOTSTRAP_TOOL_ROOT`; discovery never creates or modifies that root.

Do not turn a declarative MCP registration into an `AVAILABLE` result until
the executable, runtime compatibility, and a safe health check pass.

If explicitly approved, complete routine install/test/commit/push actions without repeated approval under AGENTS.md autonomy.

Then STOP.
