# Bootstrap Final Release Packet

Status: **READY FOR HUMAN REVIEW AND ACTIVATION**. This is not independent
human approval and is not a publication record.

## Release identity

- Branch: `release-candidate/agentterm-bootstrap-20261018`
- HEAD: `289353a` before Open Terminal integration; final Open Terminal changes
  are pending in the current release-candidate worktree.
- Worktree: `/Users/admin/codex-bootstrap-rc`
- GitHub `main`: unchanged
- Active `~/.zshrc`: unchanged
- Active Codex MCP configuration: unchanged

## Independent technical review

A separate source-level review process inspected the lifecycle, launcher,
host bridge, ledger, tool discovery, and commit history. Assertions passed for
authority ordering, read-only default launch, explicit AgentTerm approval,
session idempotence, ledger fail-closed behavior, HEAD/scope drift rejection,
and allowlisted host execution without `shell=True`.

The review found and corrected one defect: repeated initialization previously
created another session-start event. Matching existing project/authority state
now returns the existing session; mismatches fail closed. No independent human
approval has been fabricated.

## Exact launcher change

The current profile contains the older read-only `codex-bootstrap` function.
The proposed replacement is the `INSTALLED_LAUNCHER` constant in
`scripts/install_bootstrap_launcher.py`. Its exact semantic additions are:

```diff
 codex-bootstrap() {
+  local agentterm_mode=0
+  local agentterm_approved=0
+  if [ "${1:-}" = "--agentterm" ]; then
+    agentterm_mode=1
+    shift
+  fi
+  if [ "${1:-}" = "--approve-agentterm-init" ]; then
+    agentterm_approved=1
+    shift
+  fi
+  if [ "$agentterm_mode" -eq 0 ] && [ "$agentterm_approved" -eq 1 ]; then
+    printf '%s\\n' "BLOCKED_PRECONDITION: --approve-agentterm-init requires --agentterm; STOP." >&2
+    return 2
+  fi
   # existing authority clone, verification, and read-only Codex discovery
+  printf '%s\\n' "$authority_json" > "$staging/authority.json"
   codex --sandbox read-only "..."
   local codex_status=$?
+  if [ "$codex_status" -ne 0 ]; then
+    rm -R "$staging"
+    return "$codex_status"
+  fi
+  if [ "$agentterm_mode" -eq 1 ]; then
+    if [ "$agentterm_approved" -ne 1 ]; then
+      printf '%s\\n' "BLOCKED_PRECONDITION: AgentTerm initialization requires explicit --approve-agentterm-init after read-only discovery; STOP." >&2
+      rm -R "$staging"
+      return 2
+    fi
+    if [ ! -f "$canonical_checkout/scripts/bootstrap_session.py" ]; then
+      printf '%s\\n' "BLOCKED_PRECONDITION: published Bootstrap does not contain the AgentTerm lifecycle entry point; STOP." >&2
+      rm -R "$staging"
+      return 2
+    fi
+    python3 "$canonical_checkout/scripts/bootstrap_session.py" \
+      --bootstrap-root "$canonical_checkout" \
+      --project-root "$PWD" \
+      init \
+      --authority-json "$staging/authority.json"
+    local agentterm_status=$?
+    rm -R "$staging"
+    return "$agentterm_status"
+  fi
   rm -R "$staging"
   return "$codex_status"
 }
```

The installer creates a timestamped same-directory backup and refuses
unrecognized or duplicate launcher functions. It has not been run against the
live profile.

## Exact MCP change

Current configuration contains only `codebase-memory-mcp` and `rea`; there is
no conflicting api-anything entry and no credential-like setting was exposed.
The proposed minimal addition is:

```diff
 [mcp_servers.rea]
 # existing configuration remains unchanged
+[mcp_servers.api-anything]
+command = "/Users/admin/codex-bootstrap-four-tool/.bootstrap-tools/install/api-anything/node_modules/.bin/api-anything"
+args = ["mcp"]
```

Before applying it, copy `/Users/admin/.codex/config.toml` to a timestamped
same-directory backup, add only this block, run `codex mcp list`, and verify
both existing servers remain. Restart Codex and rerun discovery.

## Tool decisions

- AgentTerm: `PASS` / `AVAILABLE`.
- loadersz-core: `PASS` / `AVAILABLE`.
- MiroFish: `BLOCKED` on this host. Official source deployment requires
  Python 3.11–3.12 and `uv`; those were provisioned in isolation, but the
  pinned `torch==2.9.1` has no macOS x86_64 wheel. Upstream also documents
  Docker deployment; Docker is present, but no Docker deployment was started
  because it requires separate service/API-key authorization and was not
  qualified here.
- api-anything: `PARTIAL` / isolated CLI operational; active registration
  pending approval.
- Open Terminal: `PASS` for managed PTY and native Terminal.app new-tab launch.
  Arbitrary existing-tab attachment and native output capture remain
  unsupported and are reported explicitly.

## Verification evidence

- Bootstrap suite before Open Terminal changes: **54 passed**; current suite:
  **56 passed**.
- AgentTerm suite: **87 passed**.
- Launcher authorization suite: **15 passed**.
- Shell syntax: passed.
- Python compilation: passed.
- Git diff checks: passed.
- Tool discovery: AgentTerm `AVAILABLE`, loadersz-core `AVAILABLE`, MiroFish
  `INCOMPATIBLE`, api-anything `NOT_REGISTERED`, Open Terminal `AVAILABLE` with
  explicit native limitations.
- No protected system or device was touched.

## Next executable action

After independent human review approval, the candidate must first be
published to canonical GitHub `main`; the launcher intentionally clones and
verifies that canonical ref. Only then may owner approval authorize the
launcher installer command documented in
`BOOTSTRAP_AGENTTERM_LAUNCHER_ACTIVATION.md`, followed separately by the
api-anything MCP block above. Installing the launcher before publication would
leave AgentTerm activation fail-closed.

Rollback: restore the exact timestamped `.zshrc` or `config.toml` backup after
confirming its path and contents. Do not remove unrelated shell or MCP entries.
