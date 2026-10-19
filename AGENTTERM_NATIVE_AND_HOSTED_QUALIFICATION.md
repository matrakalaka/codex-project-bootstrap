# Native and hosted qualification

## Native macOS Keychain

Implemented artifacts:

- `vendor/agentterm/native/AgentTermKeychain.swift` uses Security.framework
  generic-password APIs for scoped create/update/read/delete.
- `vendor/agentterm/src/agentterm/keychain.py` provides a thread-safe,
  fail-closed Python wrapper. Secrets are supplied through stdin only.
- `scripts/build_keychain_helper.sh` builds the helper with a private module
  cache and no global installation.
- `vendor/agentterm/tests/test_keychain.py` covers mock lifecycle and the
  no-helper fail-closed contract.

The helper compiles with an isolated Swift module cache, and the real native
Python-wrapper lifecycle now **PASSES** using a uniquely scoped synthetic item:
CREATE, READ, UPDATE, READ, DELETE, and VERIFY ABSENCE (`errSecItemNotFound`,
`-25300`). No personal Keychain items were accessed.

Owner-run qualification:

```sh
cd /Users/admin/codex-agentterm-phase1
export SWIFT_MODULECACHE_PATH="$(mktemp -d)"
./scripts/build_keychain_helper.sh "$PWD/.build/AgentTermKeychain"
PYTHONPATH=vendor/agentterm/src \
/Users/admin/ic8-stack-qualification/.venv/bin/pytest -q \
  vendor/agentterm/tests/test_keychain.py
PYTHONPATH=vendor/agentterm/src \
/Users/admin/ic8-stack-qualification/.venv/bin/python \
  scripts/qualify_keychain_host.py --helper "$PWD/.build/AgentTermKeychain"
```

For an isolated real item, use a random account under service
`com.agentterm.test.<random>`, run put/get/delete, and remove only that exact
account. Do not use the owner account or inspect existing Keychain entries.

## Hosted synchronization

The repository contains a production-oriented HTTPS client contract and a
loopback staging service with authentication, replay protection, limits,
health/readiness, backup, and restart recovery. A public hosted deployment is
not claimed: it still requires an approved service boundary, TLS termination,
secret deployment, and production operations. The PostgreSQL adapter and local
multi-process service path are qualified below.

The current local staging command is:

```sh
PYTHONPATH=vendor/agentterm/src \
/Users/admin/ic8-stack-qualification/.venv/bin/python -m agentterm.cli \
staging-acceptance --root "$(mktemp -d)"
```

It must be run on a host permitting loopback sockets. Production activation is
blocked pending independent review and infrastructure approval.

The distributed storage contract is implemented in `postgres.py` with
transactional connection ownership, PostgreSQL primary-key replay constraints,
`FOR UPDATE` serialization, cursor tables, and `deploy/postgres-schema.sql`.
Disposable PostgreSQL 16 multi-process qualification **PASSED** using
`scripts/qualify_postgres_host.py`: two independent loopback HTTP services
shared one database, concurrent publication and pull succeeded, one service
restarted and recovered all four objects, and `pg_dump`/`pg_restore` restored
all four objects. Production deployment remains unqualified and disabled.

Host command (after starting an isolated PostgreSQL cluster and setting a
disposable DSN):

```sh
PYTHONPATH=vendor/agentterm/src .venv-hosted/bin/python \
  scripts/qualify_postgres_host.py \
  --dsn 'host=/private/tmp/agentterm-pg-sock-host port=55432 dbname=agentterm_qual user=admin'
```
