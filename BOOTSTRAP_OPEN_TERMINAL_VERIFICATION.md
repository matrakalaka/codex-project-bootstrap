# Open Terminal Verification

## Synthetic qualification

- Managed session creation: passed.
- Explicit approval denial: passed; no input was sent.
- Selected-session multiline command: passed.
- Output capture and exit status: passed.
- Session close and process cleanup: passed.
- AgentTerm ledger integration and resume: passed.
- Native mode AppleScript invocation: passed with mocked bridge coverage.

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
