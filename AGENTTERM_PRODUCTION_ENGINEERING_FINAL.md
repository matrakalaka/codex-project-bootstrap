# AgentTerm production engineering final

## Final classification

**Installable: YES. Local staging: YES on a normal host. Production deployable:
NO. Production activation: NO-GO. Independent review: READY.**

Final branch: `feature/agentterm-worktree-phase1`.

The verified rollback baseline is `d5b5630d25b95e284074caaa4f0b5f552285ff78`.
This milestone is committed after that baseline and does not modify protected
repositories or production infrastructure.

## Implemented feature matrix

| Area | Local status | Evidence |
|---|---|---|
| AgentTerm core and CLI | Implemented and tested | Existing AgentTerm suite and CLI smoke |
| Synthetic Git lifecycle | Implemented, production-disabled | `worktree.py`, adversarial lifecycle tests |
| Signed encrypted sync | Implemented and tested | `platform.py`, replay/concurrency tests |
| SQLite recovery/backup | Implemented and tested | migration, corruption, backup, restart tests |
| Loopback staging service | Implemented and host-qualified by owner | `LoopbackSyncService`, owner staging result |
| OIDC lifecycle | Synthetic provider/client implemented | `oidc.py`, PKCE/signature/rotation tests |
| Billing adapter | Synthetic provider and ordered events implemented | `billing.py`, webhook/state tests |
| Runtime/HTTPS contracts | Implemented and tested | `integration.py` |
| Native macOS Keychain | Implemented, host-qualified build blocked | Security.framework helper, Python wrapper, mock lifecycle tests |
| Hosted multi-instance sync | Not deployed | requires service/database/TLS infrastructure |
| PostgreSQL distributed store | Implemented, unqualified | `postgres.py`, `deploy/postgres-schema.sql`; no driver/server available |

## Commands

Build an isolated wheel:

```sh
/Users/admin/ic8-stack-qualification/.venv/bin/python -m pip wheel \
  --no-deps --no-build-isolation -w /tmp/agentterm-wheel ./vendor/agentterm
```

Run local staging acceptance:

```sh
PYTHONPATH=vendor/agentterm/src \
/Users/admin/ic8-stack-qualification/.venv/bin/python -m agentterm.cli \
staging-acceptance --root /tmp/agentterm-staging
```

Run the full normal-host qualification:

```sh
cd /Users/admin/codex-agentterm-phase1
./scripts/qualify_agentterm_host.sh
```

## Evidence

- AgentTerm strict suite: **128 passed, 3 skips** (two socket sandbox skips and
  one unavailable PostgreSQL driver).
- Bootstrap/security/continuity: **101 passed, 4 AF_UNIX skips**.
- Owner historical staging qualification: **36 passed, 0 failed, 0 skipped**.
- Current sandbox staging acceptance: blocked by loopback policy; not counted.
- Wheel packaging, compilation, CLI demo, health, and diff checks: passed.

The PostgreSQL adapter has not been represented as multi-instance evidence:
Docker is unavailable, no PostgreSQL server is running, and neither psycopg
driver is installed.

The Security.framework helper and fail-closed wrapper are now implemented, but
native compilation/qualification is blocked on this host by the Swift
toolchain/SDK mismatch and module-cache permissions. See
`AGENTTERM_NATIVE_AND_HOSTED_QUALIFICATION.md`.

## Remaining external gates

1. Implement and independently review a native Security.framework Keychain
   adapter using isolated test items only.
2. Configure a real OIDC provider, discovery/JWKS retrieval, authorization
   code deployment, sessions, and revocation endpoint.
3. Deploy an authenticated HTTPS service with a reviewed multi-instance
   transactional database, TLS termination, secrets, observability, backup,
   retention, and disaster recovery.
4. Connect an authorized billing sandbox and independently review webhook and
   reconciliation policy.
5. Obtain independent cryptographic/security approval and explicit approval for
   production Git mutation.

No live credentials, personal Keychain records, payment methods, public
services, protected repositories, or production Git state were accessed.
