# AgentTerm Launcher Activation

## Implemented behavior

The generated launcher in `scripts/install_bootstrap_launcher.py` now supports:

```sh
codex-bootstrap
```

for the existing read-only discovery flow, and:

```sh
codex-bootstrap --agentterm --approve-agentterm-init
```

for read-only discovery followed by project-scoped AgentTerm initialization.
The second flag is mandatory. `codex-bootstrap --agentterm` stops with
`BLOCKED_PRECONDITION` and does not create `.agentterm` state. An
`--approve-agentterm-init` flag without `--agentterm` is also rejected.

The launcher resolves and verifies authority before either path. It does not
enable YOLO mode, modify the target project during discovery, or bypass the
human approval boundary. It also prevents duplicate initialization through the
existing session-state checks.

## Current activation state

The owner's active `~/.zshrc` was **not modified**. The release candidate is
not published to GitHub `main`; therefore the currently installed launcher is
not claimed to be AgentTerm-powered.

## Proposed owner-approved installation

After independent review, publication of the approved candidate to canonical
GitHub `main`, and explicit owner approval, run from the reviewed checkout:

```sh
python3 scripts/install_bootstrap_launcher.py \
  --zshrc "$HOME/.zshrc" \
  --repo-root /path/to/the/approved/bootstrap/checkout
```

The installer accepts only a recognized existing launcher, writes a timestamped
same-directory backup before replacement, and is idempotent. To reverse the
change, restore that exact backup after confirming the target path and contents;
do not use a broad recursive cleanup. Open a new shell or source the file only
after reviewing the resulting diff.

This procedure requires separate approval because it changes a user shell
configuration. Installing before the candidate is published would leave the
read-only path usable but the AgentTerm path would fail closed because the
launcher verifies that the canonical checkout contains
`scripts/bootstrap_session.py`. It is not executed by this release candidate.
