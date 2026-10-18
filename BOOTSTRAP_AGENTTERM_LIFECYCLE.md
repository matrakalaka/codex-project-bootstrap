# Bootstrap AgentTerm Lifecycle

The canonical lifecycle is represented by
`python3 scripts/bootstrap_session.py` after Bootstrap authority resolution.

## States

```text
AUTHORITY_VERIFIED -> READY -> PLANNED -> APPROVAL_PENDING -> EXECUTING
  -> VERIFYING -> PASS | BLOCKED_PRECONDITION | FAILED_AFTER_EXECUTION | DIVERGENCE
  -> HANDOFF -> RESUMED (fresh process, same project identity and verified ledger)
```

`init` creates repository-owned `.agentterm` state and a ledger session-start
event. It does not modify project source or global configuration. `plan`
records the exact task packet, agent, scope, verification commands, and
expected HEAD. `execute` refuses to run unless its request exactly matches the
persisted plan and the HEAD is unchanged.

For mutating work, AgentTerm's runner requires explicit human confirmation.
The integration never sets AgentTerm's `yes` bypass. The runner records the
approval, invokes the selected adapter, observes Git changes, runs declared
verification, classifies the outcome, and writes a generated brief.

`resume`, `status`, and `verify` validate project identity and ledger. A
foreign project, corrupted ledger, stale rejected checkpoint, missing agent,
incompatible adapter, or changed planned HEAD fails closed.

## Entry points

```sh
python3 scripts/bootstrap_session.py init --authority-json /path/to/resolver-output.json
python3 scripts/bootstrap_session.py plan "task" --agent codex --mutate --allow 'src/**' --verify 'pytest -q'
python3 scripts/bootstrap_session.py execute "task" --agent codex --mutate --allow 'src/**' --verify 'pytest -q'
python3 scripts/bootstrap_session.py status
python3 scripts/bootstrap_session.py resume
python3 scripts/bootstrap_session.py handoff
```

The resolver's output is the authority evidence passed to the lifecycle. No
command above grants publication or privileged host access.
