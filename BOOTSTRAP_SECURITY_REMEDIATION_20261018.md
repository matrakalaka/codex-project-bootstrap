# Bootstrap Security Remediation — 2026-10-18

Status: **TECHNICALLY QUALIFIED WHERE HOST CAPABILITIES PERMITTED; PENDING
INDEPENDENT HUMAN REVIEW**.

The remediation is local-only. It does not publish, activate the launcher,
change global MCP configuration, touch devices, or modify protected systems.

## Seven-finding matrix

| Finding | Root cause | Remediation | Evidence | Residual limitation |
|---|---|---|---|---|
| 1. Unauthenticated PTY socket | Server trusted client-wrapper approval | Per-session 256-bit capability in an owner-only separate file; HMAC binds operation, project root, request ID; replay rejection; socket mode 0600; authorization audit records | `test_terminal_security_unit.py`; managed direct-socket test present | AF_UNIX integration skipped under this sandbox |
| 2. Timeout left commands running | Timeout stopped only the reader | Session shell process group is terminated with bounded TERM/KILL escalation and reaped; queued input cannot continue after confirmed termination | Process-group unit test; managed timeout test present | Full PTY timeout path requires approved-host qualification |
| 3. Non-atomic initialization | Ledger append and JSON state write were separate and unlocked | Interprocess `flock`, deterministic idempotency key, matching-event recovery, atomic state replacement, ambiguity rejection | Concurrent initializer and injected state-write crash tests | Legacy ambiguous state fails closed rather than being guessed at |
| 4. Unsafe verification commands | Arbitrary declared commands ran without authorization | Explicit authorization required; shell syntax rejected; executable must resolve to a regular file; authorization/result recorded | Verification policy tests; lifecycle mutation workflow passes | Authorized commands remain powerful and require review of the exact plan |
| 5. Corrupt ledger status success | `status` returned a false flag with exit 0 | Status raises `BLOCKED_PRECONDITION`; CLI exits nonzero; no repair/discard path | Corrupt-ledger CLI regression | Hash chains remain tamper-evident rather than tamper-proof |
| 6. Mutable terminal metadata | Plain JSON was trusted by session operations | Owner-only directory/files, atomic replacement, HMAC integrity bound to separate capability and project/session identity | Native metadata-tamper unit test; managed test present | Same-user filesystem compromise remains outside this local boundary |
| 7. Close falsely reported closed | State changed before termination was confirmed | `CLOSED`, `CLOSE_FAILED`, and `UNKNOWN` are distinct; failure preserves recovery evidence | Failed-close unit test | OS-level crash can still produce `UNKNOWN`, which blocks success claims |

## Qualification record

The Codex sandbox suite reports **74 tests, 70 passed, 4 skipped**. The skips
are managed PTY integration tests because this sandbox returns `EPERM` for
AF_UNIX `bind`; they are explicitly `NOT_RUN`, not passed. Normal macOS host
verification separately reports **74/74 PASS**, including all four managed
PTY tests and the managed Codex smoke. Native Terminal.app mock coverage,
capability authorization, replay, metadata integrity, process-group
termination, close failure, initialization concurrency/crash recovery,
verification authorization, launcher tests, authority tests, and ledger CLI
behavior passed.

Final qualification rerun on the requested commit confirmed:

    Normal macOS host: AF_UNIX PASS
    Four managed-PTY tests: 4 PASS, 0 FAIL, 0 SKIP
    Bootstrap suite: 74 PASS, 0 FAIL, 0 SKIP (74 total)
    Managed Codex CLI smoke: PASS
    Vendored AgentTerm pytest suite: BLOCKED (pytest unavailable)

The isolated environment contains `agentterm 0.1.0`, but no pytest module,
pytest executable, or local package cache was available. No global package
installation or network-dependent provisioning was attempted, and no AgentTerm
pytest pass claim is made.

## Owner-authorized normal Terminal qualification

If this Codex sandbox is still active, run the following from a normal,
owner-authorized macOS Terminal. These commands do not publish, activate the
launcher, change MCP configuration, or touch protected systems:

    cd /Users/admin/codex-bootstrap-rc
    export PYTHONPATH=scripts
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
      test_open_terminal_bridge.OpenTerminalBridgeTests.test_managed_session_is_selected_multiline_and_audited \
      test_open_terminal_bridge.OpenTerminalBridgeTests.test_direct_socket_without_capability_is_rejected \
      test_open_terminal_bridge.OpenTerminalBridgeTests.test_timeout_terminates_session_and_queued_input_cannot_run \
      test_open_terminal_bridge.OpenTerminalBridgeTests.test_tampered_metadata_is_rejected

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'
    python3 -m pytest -q vendor/agentterm/tests

For the harmless managed Codex smoke, initialize a synthetic repository with
the approved AgentTerm executable, open a managed session, submit only
codex --version, capture the returned output and returncode, close the
session, and verify the terminal_session/terminal_command records and ledger
hash chain. The smoke must be recorded as BLOCKED_PRECONDITION if AgentTerm,
Codex, or AF_UNIX is unavailable.

Python compilation and diff checks passed. The vendored AgentTerm pytest suite
is **NOT RUN** because the previously referenced isolated pytest environment
was absent and network access prevented temporary installation.

## Security boundary

## Managed PTY startup follow-up

The first owner-host verification found all four managed sessions failing
during readiness before their security assertions ran. Root cause was an
overlong macOS AF_UNIX absolute path; shortening only the basename was not
sufficient when the configured temporary directory was deep. The bridge now
uses a validated owner-only runtime root and collision-resistant per-session
directory, independent of the project path, measures the complete encoded
address, rejects symlink/permission substitutions, and refuses collisions.
Startup failures include bounded child stderr, exit status, and path length
without exposing capabilities or command input. Startup cleanup closes pipes,
reaps children, and removes only owned socket artifacts. Host AF_UNIX
integration remains to be rerun after this complete fix.

The supported path remains managed PTY or approved native new-tab launch.
Native Terminal.app output capture and arbitrary existing-tab attachment remain
unsupported. Unknown authority, socket capability, metadata integrity,
termination, AgentTerm availability, or ledger integrity fails closed.
