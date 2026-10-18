# Bootstrap Final Verification

Qualification date: 2026-10-18. Result: **PARTIAL — implementation qualified
locally; independent approval and external activation remain outstanding**.

## Evidence

- Release-candidate branch: `release-candidate/agentterm-bootstrap-20261018`.
- Final local commit: `22d6c49`, including Open Terminal integration.
- Baseline: `be9b844bfdaa89f4c695583726b72121a2621e95`.
- Isolated discovery root: `/Users/admin/codex-bootstrap-four-tool/.bootstrap-tools`.
- AgentTerm archive SHA-256: `17b6784fe8a96e7667719131209fc44ecefd56010f69479ac1b6124690e5d500`.
- Discovery: AgentTerm `AVAILABLE`; loadersz-core `AVAILABLE`; MiroFish
  `INCOMPATIBLE` after isolated `uv`/Python 3.11 provisioning because its
  lock pins `torch==2.9.1`, which has no macOS x86_64 wheel; api-anything `NOT_REGISTERED`
  because active Codex configuration was not changed; Open Terminal `AVAILABLE`
  with managed PTY and native new-tab launch, while arbitrary existing-tab
  attachment remains unsupported.
- Active `/Users/admin/.codex/config.toml` was read-only inspected and not
  modified.

## Tests

Passed during this qualification:

- Launcher installer and synthetic launcher suite: **15 tests passed**.
- Full Bootstrap regression suite: **56 tests passed**.
- Vendored AgentTerm suite: **87 tests passed** in an isolated virtual environment.
- The new launcher test verified read-only discovery, explicit two-step
  authorization, session creation, and preservation of a dirty target file.
- The denied AgentTerm launcher path returned code 2 and created no session.
- Existing AgentTerm-core synthetic lifecycle coverage remains in the source
  suite, including plan/approval, scope, ledger, resume, host bridge, and
  failure fixtures.

Remaining commands for the final reviewer to rerun from this clean candidate:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m py_compile scripts/*.py
python3 scripts/tool_discovery.py --json --tool-root /Users/admin/codex-bootstrap-four-tool/.bootstrap-tools
git diff --check
```

The full suite and vendored AgentTerm test suite must be recorded by the
independent reviewer before publication; no protected-device test is required
or permitted.

## Remaining blockers

1. Independent review and approval are pending.
2. Owner approval is required before changing `~/.zshrc`.
3. api-anything requires separate approval before active global Codex MCP
   registration; the local registration metadata remains preserved.
4. MiroFish remains incompatible until its missing runtime prerequisite is
   supplied and validated.
5. Native arbitrary-tab attachment and native output capture remain unsupported;
   managed PTY is the supported reliable alternative.
6. GitHub publication/merge authorization is not granted.

Publication must precede shell activation because the launcher resolves the
canonical GitHub `main` checkout and requires `scripts/bootstrap_session.py`
there.
