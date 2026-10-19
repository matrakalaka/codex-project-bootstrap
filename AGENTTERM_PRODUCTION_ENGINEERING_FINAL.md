# AgentTerm production engineering final

## Final classification

**Installable: YES. Local staging: YES on a normal host. Production deployable:
NO. Production activation: NO-GO. Independent review: READY.**

## Independent release decision

**Decision: A — proceed to controlled deployment preparation.** Preserve this
release candidate as the rollback baseline and continue only with isolated
staging, provider configuration, operational rehearsal, and independent
review. Do not interpret this decision as approval to expose the service or
enable production Git mutation.

The architecture is suitable for controlled staging because the local
cryptographic, Keychain, replay, PostgreSQL concurrency, backup/restore, and
TLS-boundary evidence is internally consistent. It is not yet suitable for
production activation because the hosted service has not been deployed, real
OIDC and billing providers are not connected, production operations have not
been exercised, and no independent security approval exists.

### Residual risk assessment

- **CRITICAL:** production activation lacks independent security approval and
  a reviewed deployment boundary; production Git mutation must remain
  disabled.
- **HIGH:** the real OIDC/billing provider paths, hosted secret operations,
  observability, retention, disaster recovery, and rollback have not been
  qualified in their target environment.
- **HIGH:** the service uses a shared bearer-token boundary behind TLS
  termination; token rotation, proxy policy, rate limits, and multi-instance
  operational behavior require deployment-specific review.
- **MEDIUM:** Docker deployment was not run because the local daemon was
  unavailable; the image and configuration artifacts remain available for an
  authorized staging environment.

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
| Native macOS Keychain | Implemented and host-qualified | Security.framework helper, Python wrapper, isolated synthetic create/read/update/delete/absence lifecycle |
| Hosted multi-instance sync | Locally deployable artifacts; not deployed | `scripts/run_agentterm_postgres_service.py`, `deploy/Dockerfile`, `deploy/Caddyfile.example`, PostgreSQL/TLS/secret infrastructure remains an activation gate |
| PostgreSQL distributed store | Implemented and locally multi-process qualified | `postgres.py`, `deploy/postgres-schema.sql`, `scripts/qualify_postgres_host.py`; production deployment remains unapproved |

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

- AgentTerm strict normal-host suite: **142 passed, 0 failed, 0 skipped**.
- Final candidate rerun in this environment: **141 passed, 0 failed, 1
  skipped**; the only skip was the optional PostgreSQL test because the
  qualification venv did not contain `psycopg`. The dedicated PostgreSQL
  16 multi-process qualification below passed separately.
- Hosted dependency qualification: **2 passed** for `test_postgres.py` in an
  isolated environment containing the declared `hosted` extra.
- Final candidate with the hosted dependency installed and strict
  `ResourceWarning`: **142 passed, 0 failed, 0 skipped**.
- Bootstrap/security/continuity strict suite: **74 passed, 2 subtests passed**.
- Owner historical staging qualification: **36 passed, 0 failed, 0 skipped**.
- Current sandbox staging acceptance: blocked by loopback policy; not counted.
- Wheel packaging, compilation, CLI demo, health, and diff checks: passed.
- Hosted release artifacts were added: a loopback-only PostgreSQL service
  entrypoint, unprivileged Docker image, production environment template, and
  TLS-termination example. These are locally reviewable deployment artifacts,
  not evidence of public deployment.
- Local HTTPS boundary: **PASS** with a disposable certificate and loopback
  TLS terminator; trusted health succeeded, a protected sync request with an
  invalid bearer token returned 401, and hostname validation rejected the
  wrong host. Docker deployment: **NOT VERIFIED** because its daemon was
  unavailable.

Disposable PostgreSQL 16 qualification passed with two independent HTTP service
processes sharing one database: four concurrent uploads, authenticated pulls,
health/readiness, process restart recovery, and `pg_dump`/`pg_restore` with four
restored objects. This is local staging evidence, not production deployment.

The Security.framework helper compiles with an isolated Swift module cache and
the Python wrapper passed a real isolated synthetic create/read/update/delete
lifecycle. Production activation still requires independent review and a
reviewed access-control/deployment policy. See
`AGENTTERM_NATIVE_AND_HOSTED_QUALIFICATION.md`.

## Remaining external gates

1. Independently review the native Security.framework Keychain access-control
  and deployment policy before production activation.
2. Configure a real OIDC provider, discovery/JWKS retrieval, authorization
   code deployment, sessions, and revocation endpoint.
3. Deploy an authenticated HTTPS service with a reviewed multi-instance
   transactional database, TLS termination, secrets, observability, backup,
  retention, and disaster recovery. The local TLS boundary is qualified;
  public/production infrastructure is not.
4. Connect an authorized billing sandbox and independently review webhook and
   reconciliation policy.
5. Obtain independent cryptographic/security approval and explicit approval for
   production Git mutation.

No live credentials, personal Keychain records, payment methods, public
services, protected repositories, or production Git state were accessed.
