# AgentTerm deployment artifacts

The service process is intentionally loopback-only. In a hosted deployment,
an approved HTTPS reverse proxy terminates TLS and forwards only to the local
service. The service itself validates bearer authentication, signed encrypted
envelopes, device trust, tenant/project binding, replay state, and PostgreSQL
transactions.

## Local qualification

Run the complete normal-host qualification from the repository root:

```sh
./scripts/qualify_agentterm_host.sh
```

For the PostgreSQL multi-process check, start a disposable PostgreSQL cluster,
then run:

```sh
PYTHONPATH=vendor/agentterm/src python scripts/qualify_postgres_host.py \
  --dsn 'postgresql://agentterm@127.0.0.1:55432/agentterm'
```

The script starts two independent HTTP processes and verifies concurrent
publication, authenticated pull, cursor persistence, restart recovery, and
shared durable state. It does not configure or start PostgreSQL.

## Hosted packaging

`Dockerfile` packages the service with the `hosted` dependency extra and runs
as an unprivileged UID. Copy `agentterm-production.env.example` into the
approved secret/configuration mechanism, replace every example value, and
provide a public trust registry containing only approved public keys. Build
and run the image with the environment and registry mounted read-only.

`Caddyfile.example` is a TLS-termination example only. Replace the hostname,
certificate policy, network policy, logging destination, and deployment
identity through the approved operations process. Do not expose the loopback
service directly.

## Release gates

Production requires a reviewed PostgreSQL deployment, TLS and secret
operations, backups and restore verification, retention and monitoring,
provider configuration, independent security approval, and explicit approval
for production Git mutation. The example files cannot enable those gates and
must not be treated as a production configuration.
