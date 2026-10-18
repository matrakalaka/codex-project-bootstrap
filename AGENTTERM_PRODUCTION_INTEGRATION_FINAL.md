# AgentTerm production integration final

Status: **GO for independent review; NO-GO for production activation**.

## Checkpoint

- Branch: `feature/agentterm-worktree-phase1`
- Baseline preserved: `d5b5630d25b95e284074caaa4f0b5f552285ff78`
- Current integration work is being performed in the same authorized worktree;
  no additional worktree was technically necessary.

## Integrated local capabilities

The local installable package combines the governed AgentTerm core, synthetic
Git worktree isolation, signed AES-GCM synchronization, durable SQLite replay
state, offline retry, tenant-scoped team authorization, entitlement metering,
health/backup diagnostics, and real disposable-repository acceptance flows.

`agentterm.integration` adds provider-independent production contracts:

- `RuntimeConfig` rejects unsafe production URLs, unbounded payloads, disabled
  keychain requirements, and production Git mutation activation;
- `OIDCValidator` validates issuer, audience, subject, tenant claims, expiry,
  and nonce after an external signature-verification layer;
- `BillingWebhookVerifier` verifies Ed25519 signatures, timestamps, event IDs,
  and replay; and
- `HttpsSyncTransport` requires HTTPS, bearer authentication, bounded bodies,
  certificate verification, and structured transport errors.

These adapters do not claim live provider, Keychain, hosted service, or
deployment verification.

## User-facing local workflow

```sh
PYTHONPATH=vendor/agentterm/src agentterm platform-demo --root /tmp/agentterm-demo
PYTHONPATH=vendor/agentterm/src agentterm platform-health /tmp/agentterm-demo
```

The demo performs real local encrypted sync, concurrent publication,
conflict/replay handling, team revocation, entitlement gating, backup,
restart recovery, disposable Git merge, and unknown-state blocking.

## Qualification

- AgentTerm strict suite: 126 passed, 2 sandbox loopback skips.
- Synthetic OIDC/billing integration: 2 passed.
- Staging acceptance test: sandbox-blocked/skipped because loopback bind is
  denied; host execution is provided by `scripts/qualify_agentterm_host.sh`.
- Repository regression: 101 passed, 4 AF_UNIX sandbox skips.
- Owner normal-host targeted qualification: 30 passed, 0 skipped, 0 failed.
- Compilation, wheel packaging, CLI acceptance, and diff checks: passed.
- `scripts/qualify_agentterm_host.sh` provides one-command normal-host
  qualification for the targeted tests and staging acceptance.

## External gates

Independent cryptographic review, native macOS Keychain implementation review,
real OIDC provider configuration, hosted service deployment, database/secret
operations, billing-provider credentials, retention/incident controls, and
explicit production Git mutation approval remain required. No production
activation, public deployment, live billing, or protected-repository mutation
is authorized by this document.
