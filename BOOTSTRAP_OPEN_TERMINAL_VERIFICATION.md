# Open Terminal Verification

## Synthetic qualification

- Managed session creation, explicit approval denial, selected-session
  multiline input, output/status capture, close/cleanup, and AgentTerm ledger
  integration tests are present but **NOT RUN** in this sandbox because AF_UNIX
  bind returns `EPERM`.
- Native mode AppleScript invocation: passed with mocked bridge coverage.
- Managed PTY `codex --version`: passed; Codex CLI `0.163.0` output and exit
  status were captured in the selected session.
- Capability, replay, cross-project, metadata-integrity, process-group
  termination, and failed-close unit coverage: passed.
- Managed socket integration tests are present but were explicitly skipped in
  the isolated Codex sandbox because AF_UNIX `bind` returns `EPERM`; this is
  `NOT_RUN`/unverified host evidence, not a pass claim. The socket location is
  configurable with `CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR` for approved hosts.

## Native macOS smoke test

On this host, `Terminal.app` exists and `osascript` can address it. A harmless
native command:

```text
/bin/printf 'BOOTSTRAP_NATIVE_TERMINAL_SMOKE\n'; exit
```

was launched in a new Terminal.app tab and returned window identifier `9523`.
The command exits immediately; native stdout was intentionally not claimed or
captured. This is `HOST-QUALIFIED` for new-tab launch only, not arbitrary-tab
attachment, native output capture, or native window close.

## Permission behavior

Terminal.app automation is governed by macOS Automation/Accessibility policy.
If `osascript` returns an authorization error, the bridge reports
`BLOCKED_PRECONDITION` and does not fall back to an active-window guess. The
owner must grant the invoking application permission in System Settings →
Privacy & Security → Automation/Accessibility as prompted by macOS.

The managed PTY path uses a dedicated local process and does not require
Terminal.app Automation permission.

## Final qualification attempt

On the requested candidate, a fresh AF_UNIX probe returned
PermissionError: [Errno 1] Operation not permitted. The four managed-PTY
integration tests therefore resulted in 0 PASS, 0 FAIL, 4 SKIP. No managed
Codex CLI smoke was claimed. The capability/replay/cross-session, timeout,
metadata, and close semantics remain covered by the passing non-socket unit
tests; host integration remains BLOCKED_PRECONDITION until rerun from a
normal owner-authorized macOS Terminal.
