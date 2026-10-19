# AgentTerm staging end-to-end report

## Status

The isolated staging workflow is implemented locally. It uses a loopback-only
ephemeral HTTP service and synthetic OIDC and billing providers. It is not a
public deployment and does not establish production TLS, hosted identity,
payment processing, or multi-instance database qualification.

## Startup and acceptance

Run the owner-qualified host workflow from Terminal.app:

```sh
cd /Users/admin/codex-agentterm-phase1
./scripts/qualify_agentterm_host.sh
```

The script runs the targeted managed-terminal, sync, and integration tests,
then executes `agentterm staging-acceptance` against a temporary evidence
directory. The command exercises authenticated HTTP sync, concurrent sequence
publication, synthetic OIDC tenant validation, signed billing webhook
verification, health/readiness behavior, backup restoration, and service
restart recovery.

## Local evidence

- Strict normal-host AgentTerm suite: 142 passed, 0 failed, 0 skipped.
- Synthetic OIDC and billing suite: 2 passed, covering PKCE, token signatures,
  JWKS rotation, ordered subscription events, payment failure, and duplicate
  event rejection.
- Bootstrap/security/continuity strict regression: 74 passed, 2 subtests passed.
- PostgreSQL 16 multi-process qualification: passed; two HTTP service
  processes shared one database, then restart and backup/restore succeeded.
- Sandbox staging HTTP acceptance: blocked by loopback bind policy; not passed.
- Packaging, compilation, CLI demo, and diff checks: passed.

## Feature classification

Implemented locally: synthetic staging service, health/readiness endpoints,
graceful lifecycle, encrypted sync, replay protection, backup/restore,
provider-independent OIDC and billing contracts, and the qualification script.

Still externally blocked: independent Keychain access-control review, real OIDC
discovery/JWKS and authorization-code exchange, hosted deployment beyond local
staging, payment provider accounts,
retention/incident operations, independent security review, and production Git
mutation approval.

## Rollback and cleanup

The staging script uses a temporary directory and removes it on exit. Local
service state can be restored from the generated SQLite backup using
`LocalSyncServer`; unknown or dirty Git worktrees are never automatically
deleted. Production rollback remains an approval-controlled operational gate.
