# Open Terminal Architecture

Open Terminal is a Bootstrap-owned capability, not an unverified external
provider. AgentTerm remains the single project-scoped session and audit owner.

## Modes

1. **Managed PTY** (`mode=managed`): Bootstrap starts a dedicated `/bin/zsh -f
   -i` under a private Unix socket. The session has a generated identity,
   project-root binding, reviewed command submission, multiline input,
   bounded timeout, output capture, exit status, close, and recovery metadata.
   This is the reliable execution mode.
2. **Native Terminal.app** (`mode=native`): Bootstrap invokes `osascript` with
   argv-separated text and asks Terminal.app to create a new tab. The returned
   window identifier is recorded. This mode does not attach to arbitrary
   existing tabs, capture native output, or close an arbitrary native window.

## Boundaries

Every open, submit, and close operation requires explicit approval and is
recorded in the AgentTerm ledger. Managed input is sent only to the selected
session's private socket. No active-window guessing, YOLO mode, unrestricted
shell bridge, or global MCP change is involved.

macOS Automation/Accessibility permissions remain OS-owned. If AppleScript is
denied, native mode returns `BLOCKED_PRECONDITION`; managed PTY mode remains
available where local process execution is permitted.
