# Bootstrap AgentTerm End-to-End Verification

`scripts/test_agentterm_bootstrap.py` exercises a temporary Git repository and
a harmless fake agent. It verifies:

- authority revision/hash and executable health are required;
- initialization creates project-scoped AgentTerm memory;
- planning persists exact task identity, scope, verification, and HEAD;
- execution requires a matching plan and explicit human confirmation;
- the fake agent changes only an allowed synthetic file;
- independent verification produces `PASS` evidence;
- ledger integrity and fresh-process resume succeed;
- approval denial performs no execution;
- cross-project resume and tampered ledger entries are rejected;
- host execution uses the existing allowlisted bridge and fails closed until
  the owner-approved environment gate is present.

## Regression commands

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'
.bootstrap-tools/install/agentterm-venv/bin/pytest -q vendor/agentterm/tests
git diff --check
```

The integration qualification produced 5 lifecycle tests and 50 Bootstrap
tests passing, plus the existing AgentTerm package suite passing after the
task/correlation identity extension. Tests are synthetic and
`UNIT/INTEGRATION-QUALIFIED`; they do not prove live Terminal.app behavior,
MCP activation, production deployment, or Android/device safety.

## Known boundaries

- Native Open Terminal remains unsupported without an exact provider identity.
- api-anything remains `NOT_REGISTERED` until separately approved global Codex
  configuration is changed.
- MiroFish remains incompatible with the observed upstream prerequisites.
- Host bridge tests use `fixture_echo` and synthetic Git repositories only.
