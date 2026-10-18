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
