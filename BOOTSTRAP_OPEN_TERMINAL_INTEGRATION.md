# Open Terminal Integration

The canonical lifecycle exposes three operations through
`scripts/bootstrap_session.py`:

```sh
python3 scripts/bootstrap_session.py --project-root PROJECT terminal-open \
  --mode managed --approve
python3 scripts/bootstrap_session.py --project-root PROJECT terminal-submit SESSION \
  --text $'printf "line-one\\nline-two\\n"' --approve
python3 scripts/bootstrap_session.py --project-root PROJECT terminal-close SESSION --approve
```

The lifecycle first verifies the project-scoped AgentTerm session. It then
delegates to `open_terminal_bridge.py` and appends `terminal_session` and
`terminal_command` events to the same AgentTerm ledger used for plans,
approvals, execution, verification, and handoff.

Managed requests use an owner-only capability kept separately from public
session metadata. The server authenticates the operation, project root,
request identifier, and capability before accepting `ping`, `submit`, or
`close`; reused request identifiers are rejected. Metadata changes are
integrity-checked and atomic. A timed-out command terminates the managed
session process group, drains no later queued command, and reports
`TIMED_OUT_TERMINATED` only after reaping succeeds. Close reports `CLOSED`
only after confirmed termination; otherwise it preserves `CLOSE_FAILED` or
`UNKNOWN` recovery state.

Native launch is intentionally separate from managed execution:

- supported: opening a new Terminal.app tab with an approved command;
- supported: managed PTY command input, multiline text, output, status, and
  session recovery;
- unsupported: attaching to an arbitrary preexisting Terminal tab;
- unsupported: capturing output from native Terminal.app tabs;
- unsupported: closing an arbitrary native Terminal.app window through the
  bridge; its lifecycle remains owned by Terminal.app;
- unsupported: injecting text into an existing Codex session owned by another
  process.

The managed PTY is the supported alternative for reliable Codex CLI workflows:
start Codex inside the selected managed session, then submit reviewed input to
that session identity. Bootstrap does not claim control over an already-open
Codex process.
