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

Current host qualification is **BLOCKED**, not passed. The host compiler could
not build the helper because the Swift module cache under `/Users/admin/.cache`
was not writable and the installed Swift compiler patch level does not match
the SDK module version. No personal Keychain items were accessed.

After rebuilding with an isolated cache, a minimal independent
Security.framework probe and the AgentTerm helper both returned
`errSecParam (-50)` for synthetic generic-password mutation in this execution
environment. This indicates the current process/keychain boundary is not
authorized for item mutation; it is not counted as native lifecycle success.

Owner-run qualification after selecting a matching Xcode toolchain:

```sh
cd /Users/admin/codex-agentterm-phase1
export SWIFT_MODULECACHE_PATH="$(mktemp -d)"
./scripts/build_keychain_helper.sh "$PWD/.build/AgentTermKeychain"
PYTHONPATH=vendor/agentterm/src \
/Users/admin/ic8-stack-qualification/.venv/bin/pytest -q \
  vendor/agentterm/tests/test_keychain.py
```

For an isolated real item, use a random account under service
`com.agentterm.test.<random>`, run put/get/delete, and remove only that exact
account. Do not use the owner account or inspect existing Keychain entries.

## Hosted synchronization

The repository contains a production-oriented HTTPS client contract and a
loopback staging service with authentication, replay protection, limits,
health/readiness, backup, and restart recovery. A hosted multi-instance server
and PostgreSQL adapter are **not claimed**: they require an approved service
boundary, TLS termination, secret deployment, and distributed database
qualification. SQLite evidence remains single-host only.

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
No PostgreSQL server or driver is installed in this environment, and Docker is
not running, so multi-instance consistency is **BLOCKED/UNQUALIFIED**, not
passed.
The store exposes the same upload/pull/health surface used by the local HTTP
service, but no production process entrypoint is enabled without a durable
trust-registry and secret-management deployment decision.
