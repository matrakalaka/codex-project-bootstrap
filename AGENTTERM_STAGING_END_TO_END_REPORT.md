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

- Strict AgentTerm suite after staging additions: 124 passed, 2 sandbox skips
  (loopback transport and staging acceptance).
- Repository regression: 101 passed, 4 AF_UNIX sandbox skips.
- Owner normal-host targeted baseline: 30 passed, 0 skipped, 0 failed.
- Sandbox staging HTTP acceptance: blocked by loopback bind policy; not passed.
- Packaging, compilation, CLI demo, and diff checks: passed.

## Feature classification

Implemented locally: synthetic staging service, health/readiness endpoints,
graceful lifecycle, encrypted sync, replay protection, backup/restore,
provider-independent OIDC and billing contracts, and the qualification script.

Still externally blocked: native Security.framework Keychain qualification,
real OIDC discovery/JWKS and authorization-code exchange, hosted multi-instance
deployment, production database coordination, payment provider accounts,
retention/incident operations, independent security review, and production Git
mutation approval.

## Rollback and cleanup

The staging script uses a temporary directory and removes it on exit. Local
service state can be restored from the generated SQLite backup using
`LocalSyncServer`; unknown or dirty Git worktrees are never automatically
deleted. Production rollback remains an approval-controlled operational gate.
