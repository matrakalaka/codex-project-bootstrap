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

The Bootstrap unittest suite reports **68 tests, 64 passed, 4 skipped**. The
skips are managed PTY integration tests because this sandbox returns `EPERM`
for AF_UNIX `bind`, including a project-local configurable socket directory.
They are explicitly `NOT_RUN`, not passed. Native Terminal.app mock coverage,
capability authorization, replay, metadata integrity, process-group
termination, close failure, initialization concurrency/crash recovery,
verification authorization, launcher tests, authority tests, and ledger CLI
behavior passed.

Python compilation and diff checks passed. The vendored AgentTerm pytest suite
is **NOT RUN** because the previously referenced isolated pytest environment
was absent and network access prevented temporary installation.

## Security boundary

The supported path remains managed PTY or approved native new-tab launch.
Native Terminal.app output capture and arbitrary existing-tab attachment remain
unsupported. Unknown authority, socket capability, metadata integrity,
termination, AgentTerm availability, or ledger integrity fails closed.
