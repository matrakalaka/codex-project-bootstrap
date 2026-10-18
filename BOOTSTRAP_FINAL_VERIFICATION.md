# Bootstrap Final Verification

Qualification date: 2026-10-18. Result: **PARTIAL — remediation qualified by
available local evidence; independent approval and external activation remain
outstanding**.

## Evidence

- Release-candidate branch: `release-candidate/agentterm-bootstrap-20261018`.
- Final local commit: the local remediation commit containing this packet.
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
- Remediation tests cover capability authentication/replay, metadata
  integrity, process-group termination, close failure state, concurrent and
  interrupted initialization, verification authorization, and corrupt-ledger
  CLI failure.

## Tests

Passed during this qualification:

- Bootstrap/security regression suite: **68 tests run, 64 passed, 4 skipped**.
  The four skips are managed-PTY host tests; AF_UNIX bind is denied by this
  Codex sandbox and therefore remains unverified here.
- Vendored AgentTerm suite: **NOT RUN**. The previously cited isolated
  environment was absent and network access prevented installing pytest into a
  temporary environment; no pass claim is made.
- Managed Codex CLI smoke: BLOCKED_PRECONDITION / NOT RUN because the same
  AF_UNIX restriction prevented opening a managed session.
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

The vendored AgentTerm suite must be recorded by the independent reviewer
before publication; no protected-device test is required or permitted.

The exact owner-authorized normal-Terminal rerun commands and the managed
Codex smoke procedure are recorded in
BOOTSTRAP_SECURITY_REMEDIATION_20261018.md.

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
