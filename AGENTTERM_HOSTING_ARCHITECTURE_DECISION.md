# AgentTerm hosting architecture decision

Date: 2026-10-19

## Decision

**Recommended production architecture: B — private Linux VPS for the
application boundary, with Caddy on the same host and PostgreSQL on an
approved private managed database or separately isolated PostgreSQL host.**

**Recommended staging architecture: the existing local-process equivalent**:
disposable PostgreSQL, two independent AgentTerm service processes, and a
loopback TLS terminator. The repository Docker image remains the reproducible
artifact for a future Linux staging host; Docker was not runtime-qualified on
the development Mac because its daemon was unavailable.

This is deployment preparation, not production approval. Public exposure,
provider accounts, DNS, paid resources, real OIDC/billing credentials, and
production Git mutation remain disabled.

## Why this fits the current implementation

The service currently enforces loopback binding and is designed to sit behind a
trusted local TLS terminator. Caddy can terminate TLS on the VPS while the
AgentTerm service listens only on `127.0.0.1`; PostgreSQL remains reachable
only over the private network. This preserves the qualified trust boundary
without introducing provider-specific ingress code.

The application is a small Python service with PostgreSQL transactions,
versioned schema initialization, durable replay constraints, health endpoints,
and a single service image. A VPS keeps the operational topology explicit:

```text
Internet/VPN -> firewall :443 -> Caddy/TLS -> 127.0.0.1:8765
                                      |
                                      +-> private PostgreSQL :5432
```

The service account has no shell privileges, no private signing keys, and no
public database listener. Secrets are injected through the host secret
mechanism/environment boundary; they are not committed or logged.

## Alternatives

| Option | Fit | Decision |
|---|---|---|
| Managed application hosting | Low operational burden and built-in ingress, but the current loopback-only service would need a provider-specific ingress/bind design and provider network assumptions. | Defer until a provider-specific boundary is reviewed. |
| Private VPS | Matches the existing Caddy/loopback/Docker artifacts, predictable topology and cost, straightforward rollback. Requires patching, monitoring, firewall, and backup operations. | **Recommended for the initial controlled deployment.** |
| Private Mac/server | Useful for development or private staging, but weak for unattended availability, patching, failover, and operational recovery. | Staging only. |
| Managed Kubernetes | Provides orchestration and scaling, but adds cluster, ingress, secret, network-policy, and database-operations complexity not justified by the current single service. | Defer until measured scale requires it. |

## Cost assumptions

These are planning estimates, not quotes or authorization to spend.

- DigitalOcean documents Droplets starting at $4/month and lists a small
  production-capable general-purpose example at $63/month; its managed
  PostgreSQL documentation lists single-node clusters from $15/month and HA
  clusters from $30/month per primary and matching standby. A minimal initial
  topology therefore has a broad planning floor of roughly $19/month before
  backups, traffic, monitoring, taxes, and a suitable production size; an HA
  database is at least roughly $60/month before those additions.
- Render documents a $7/month 0.5 CPU/512 MB service plan and managed
  PostgreSQL, backups, private networking, and TLS, but the selected database
  plan, storage, bandwidth, and service scaling determine the actual total.
- AWS App Runner and RDS/EKS are usage-priced. AWS documents App Runner
  per-resource CPU/memory billing and EKS at $0.10/hour per cluster before
  worker, database, storage, logging, network, and public-IP costs. That is a
  poor initial cost/complexity fit without an existing AWS operating model.
- Hetzner documents transparent hourly/monthly VM pricing and private-network
  options, but the operator would own the database, backups, monitoring, and
  recovery unless separate managed services are added.

Sources checked 2026-10-19:

- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets)
- [DigitalOcean PostgreSQL pricing](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/)
- [Render pricing](https://render.com/pricing)
- [Render PostgreSQL operations](https://render.com/docs/postgresql)
- [AWS App Runner pricing](https://aws.amazon.com/apprunner/pricing/)
- [AWS EKS pricing](https://aws.amazon.com/eks/pricing/)
- [Hetzner cloud server overview](https://docs.hetzner.com/cloud/servers/overview/)

## Deployment preparation implemented

- `deploy/Dockerfile` provides an unprivileged image with the hosted
  PostgreSQL dependency.
- `scripts/run_agentterm_postgres_service.py` validates production HTTPS
  configuration, loopback binding, public trust registry loading, schema
  initialization, and graceful shutdown.
- `deploy/Caddyfile.example` defines the TLS-to-loopback boundary.
- `deploy/agentterm-production.env.example` defines secret/configuration
  injection without real values.
- `deploy/agentterm.service.example` defines a least-privilege Linux service
  boundary.
- `scripts/qualify_postgres_host.py` exercises independent processes,
  concurrent publication, pull, cursor persistence, and restart recovery.

## Rollout and rollback

1. Build and hash the wheel/image from the committed candidate.
2. Provision a private staging VPS/database with no production data.
3. Inject synthetic trust registry, bearer token, database URL, and test TLS
   certificate through the approved secret mechanism.
4. Run migrations, health/readiness checks, HTTPS smoke tests, concurrent sync,
   backup/restore, and restart recovery.
5. Record the image, schema, configuration, and database backup identifiers.
6. Promote only after independent review and owner approval.
7. Roll back by stopping new traffic at Caddy, restoring the previous image and
   compatible schema/configuration, then verifying health and cursor/replay
   state. Never delete unknown or dirty worktrees or roll a schema backward
   without a tested migration plan.

## Remaining gates

- Independent security review of cryptography, Keychain, proxy trust, tenant
  isolation, and Git mutation boundaries.
- Provider-specific OIDC and billing sandbox configuration and qualification.
- Approved VPS/database account, private networking, secret manager, DNS/TLS,
  monitoring, retention, backup, incident response, and DR ownership.
- Target-host deployment and rollback rehearsal.
- Explicit production activation approval; production Git mutation remains
  fail-closed.

Final classification: **controlled deployment preparation GO; production
activation NO-GO**.
