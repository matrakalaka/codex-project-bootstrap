# AgentTerm local quickstart

AgentTerm is enabled per project and does not require Docker, PostgreSQL, a
hosted service, shell-profile changes, or a global default change.

## Start in an existing Bootstrap project

From the project directory, run the repository-owned launcher:

```sh
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local doctor
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local init --write-manifest
```

`init` creates only the project-local `.agentterm/` ledger area and optional
manifest. It does not rewrite Bootstrap authorities, playbooks, Git history,
or project configuration.

## Run a bounded Codex task

Set the project objective once, then run a task with an explicit mutation
scope and host verification command:

```sh
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local objective set \
  "Describe the project objective" --proof "What proves it" \
  --stop "When the task must stop"

/Users/admin/codex-agentterm-phase1/scripts/agentterm-local run \
  --agent codex --mutate --allow 'src/**' --forbid '.agentterm/**' \
  --verify 'python3 -c "print(\"verified\")"' \
  --playbook BUG_FIX "Describe one bounded task"
```

Review the approval prompt before allowing the edit. Use `--yes` only in a
disposable, automated fixture where the exact scope is already controlled.

## Inspect, verify, and resume

```sh
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local status
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local verify
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local log
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local search "keyword"
/Users/admin/codex-agentterm-phase1/scripts/agentterm-local checkpoint --publish
```

The ledger is hash-chained. `verify` checks its integrity; `status` and
`search` reconstruct usable context for the next session. For Bootstrap-owned
authority and lifecycle control, the existing `scripts/bootstrap_session.py`
bridge remains available and continues to enforce Bootstrap authority,
approval, scope, and host verification.

## Optional convenience installation

No installation is required when using the absolute launcher above. If a
project needs an isolated `agentterm` entry point, create a project-local
virtual environment and install the vendored package using the project's
normal dependency policy:

```sh
python3 -m venv .agentterm-venv
.agentterm-venv/bin/python -m pip install -e \
  /Users/admin/codex-agentterm-phase1/vendor/agentterm
.agentterm-venv/bin/agentterm doctor
```

This is optional and reversible; it does not alter global Python, PATH, shell
profiles, or Codex settings. Do not commit `.agentterm-venv/`.

## Disable and return to Bootstrap

Export or preserve the local ledger, then move only the project-local
metadata aside:

```sh
mv .agentterm .agentterm.disabled-$(date +%Y%m%d%H%M%S)
```

Continue using the existing Bootstrap commands. Restore the `.agentterm/`
directory to resume AgentTerm. Do not perform this operation in a protected or
active project without authorization.

## Troubleshooting

Use an explicit interpreter without changing global configuration:

```sh
AGENTTERM_PYTHON=/path/to/python \
  /Users/admin/codex-agentterm-phase1/scripts/agentterm-local doctor
```

If `doctor` cannot find Codex, verify the `codex` executable is available in
the process environment. AgentTerm does not install or alter agent CLIs.
