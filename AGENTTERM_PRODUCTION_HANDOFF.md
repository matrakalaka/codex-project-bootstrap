# AgentTerm production handoff

## Recommendation

**GO for independent human security review. NO-GO for production activation.**

The Phase 1 worktree engine and local platform services are implemented in the
existing development worktree. The local CLI demonstration is real and uses
temporary Git fixtures, encrypted signed envelopes, team authorization,
revocation, entitlements, conflict detection, and conservative recovery.

## Owner-authorized next actions

1. Run the root regression and AF_UNIX tests on a normal supported macOS host
   using the documented isolated environment.
2. Obtain independent approval for the cryptographic and mutation boundaries.
3. Select and approve OS keychain/KMS, authenticated transport, retention,
   billing, and incident-response designs.
4. Only after those approvals, create a separately authorized production
   qualification plan. Do not enable the current production adapter directly.

No publication, deployment, live billing, protected-repository mutation, or
launcher activation is authorized by this handoff.

## Required requalification after SQLite fix

The previous normal-host failure was a cross-thread SQLite connection defect.
It is fixed in the current source. Rerun the following on normal macOS with
loopback permission before treating transport qualification as complete:

```sh
cd /Users/admin/codex-agentterm-phase1
PYTHONPATH=vendor/agentterm/src /Users/admin/ic8-stack-qualification/.venv/bin/pytest -q scripts/test_open_terminal_bridge.py vendor/agentterm/tests/test_platform.py -rs
```
