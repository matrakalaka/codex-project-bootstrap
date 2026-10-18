# api-anything MCP Registration Proposal

Status: **NOT APPLIED — explicit owner approval required**.

The local structural registration is already present in
`tooling/mcp.registration.json`. The proposed active Codex entry is:

```toml
[mcp_servers.api-anything]
command = "/Users/admin/codex-bootstrap-four-tool/.bootstrap-tools/install/api-anything/node_modules/.bin/api-anything"
args = ["mcp"]
```

Before application, the owner-approved operator must:

1. Copy `/Users/admin/.codex/config.toml` to a timestamped same-directory
   backup and verify that backup is readable.
2. Add only the TOML block above, preserving every existing section.
3. Validate with `codex mcp list` and confirm the existing
   `codebase-memory-mcp` and `rea` entries remain present.
4. Restart Codex and rerun Bootstrap discovery.

Bootstrap has not changed the global file. The isolated CLI passed its version,
help, build, MCP EOF-startup, and upstream test checks, but that does not make
it active in a newly launched Codex session until this approved registration is
applied.

Rollback is surgical: restore the verified timestamped backup after confirming
the target path; do not remove unrelated MCP sections.
