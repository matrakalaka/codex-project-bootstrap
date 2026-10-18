# Open Terminal Architecture

Open Terminal is a Bootstrap-owned capability, not an unverified external
provider. AgentTerm remains the single project-scoped session and audit owner.

## Modes

1. **Managed PTY** (`mode=managed`): Bootstrap starts a dedicated `/bin/zsh -f
   -i` under a private Unix socket. The session has a generated identity,
   project-root binding, a separate owner-only capability file, authenticated
   non-replayable requests, reviewed command submission, multiline input,
   bounded output and timeout, process-group cancellation, exit status, close,
   and recovery metadata. A timeout terminates the session before reporting
   `TIMED_OUT_TERMINATED`; unconfirmed termination is never reported as
   success. This is the reliable execution mode.
2. **Native Terminal.app** (`mode=native`): Bootstrap invokes `osascript` with
   argv-separated text and asks Terminal.app to create a new tab. The returned
   window identifier is recorded. This mode does not attach to arbitrary
   existing tabs, capture native output, or close an arbitrary native window.

## Boundaries

Every open, submit, and close operation requires explicit approval and is
recorded in the AgentTerm ledger. The managed server independently authenticates
each request with a session-bound capability, rejects replay, and records
authorization decisions without recording the capability. Metadata is signed,
atomically replaced, and owner-only. Managed input is sent only to the selected
session's private socket. No active-window guessing, YOLO mode, unrestricted
shell bridge, or global MCP change is involved.

macOS Automation/Accessibility permissions remain OS-owned. If AppleScript is
denied, native mode returns `BLOCKED_PRECONDITION`; managed PTY mode remains
available where local process execution is permitted.
