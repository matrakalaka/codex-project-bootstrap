# Production activation checklist

Activation remains **NO-GO** until every gate is independently signed off.

- [ ] Independent review approves cryptographic provider and envelope protocol.
- [ ] OS-backed private-key storage, rotation, revocation, and recovery are
      implemented and tested without exporting secrets.
- [ ] OIDC discovery/JWKS, authorization-code/PKCE, session, logout, and
      provider outage behavior are configured and independently reviewed.
- [ ] Billing-provider sandbox reconciliation, refunds, failed payments, and
      signed webhook ordering are independently reviewed.
- [ ] Authenticated transport, server identity, tenant isolation, limits, and
      operational logging are reviewed.
- [ ] Production worktree adapter receives explicit approval and remains
      disabled until then.
- [ ] Normal-host AF_UNIX managed-terminal qualification passes.
- [ ] Crash/recovery and migration qualification passes on the target host.
- [ ] Billing, retention, incident response, backup, and rollback policies are
      approved.
- [ ] No protected checkout, production credential, device, or launcher is
      changed during activation preparation.
- [ ] Rollback rehearsal restores application state without deleting unknown or
      dirty worktrees.
