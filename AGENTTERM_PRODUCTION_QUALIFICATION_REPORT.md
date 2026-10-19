# AgentTerm production qualification report

## Local results

- AgentTerm normal-host tests: **142 PASS**, **0 FAIL**, **0 SKIP**.
- Strict `ResourceWarning`: **142 PASS**, **0 FAIL**, **0 SKIP**.
- Final candidate rerun in the available qualification environment: **141
  PASS**, **0 FAIL**, **1 SKIP**; the skip was `test_postgres.py` because the
  selected venv did not contain the optional `psycopg` dependency. The
  PostgreSQL-specific qualification was run separately against PostgreSQL 16
  and passed.
- Optional PostgreSQL test with the isolated hosted dependency: **2 PASS**.
- Bootstrap/security/continuity strict regression: **74 PASS**, **2 subtests PASS**.
- AF_UNIX and loopback HTTP tests: included in the normal-host result above.

## Host defect record

Normal macOS qualification previously produced 24 passed and 1 failed. The
failure was the real threaded loopback upload path: a SQLite connection owned
by the construction thread was reused by an HTTP worker thread. The corrected
implementation uses per-operation connections and explicit transactions. The
corrected implementation was subsequently host-qualified in the 142-test
result above.

The follow-up host failure was caused by strict highest-sequence arrival
enforcement. Concurrent valid publications from one device were not replay,
but their HTTP arrival order was nondeterministic. The fix uses bounded
out-of-order acceptance with durable per-device uniqueness and explicit
`SequenceConflict`/`StaleEnvelope` classifications. The corrected bounded
window was subsequently host-qualified in the 142-test result above.
- Compilation: **PASS**.
- `git diff --check`: **PASS**.
- CLI integration: `platform-demo` completed signed encrypted sync, conflict
  detection, team revocation, entitlement gating, real disposable worktree
  merge, backup, offline retry, restart/idempotent replay, health inspection,
  and blocked unknown recovery. `platform-health` reported SQLite integrity
  `ok`, schema version `2`, and two stored objects.
- Packaging: **PASS**; a no-dependency `agentterm-0.1.0-py3-none-any.whl`
  was built in the isolated environment.
- Integration contracts: **5 PASS**; runtime configuration, OIDC claims,
  signed billing webhooks, replay rejection, and HTTPS transport fail-closed
  behavior.
- Synthetic OIDC/billing integration: **2 PASS**; PKCE authorization-code
  exchange, signed token validation, key rotation, ordered subscription state,
  failed-payment handling, and duplicate-event rejection.
- Staging acceptance: **BLOCKED/SKIP** in the sandbox because the actual
  loopback bind is denied; the owner-run script is provided for host evidence.
- Native Keychain helper compilation: **PASS** with an isolated Swift module
  cache; Python-wrapper synthetic lifecycle: **PASS** (create/read/update/read/
  delete/absence, with random service/account cleanup).
- PostgreSQL multi-process qualification: **PASS** against disposable PostgreSQL
  16. Two independent HTTP service processes shared one database; concurrent
  uploads, pulls, restart recovery, and backup/restore all passed. The exact
  command is `scripts/qualify_postgres_host.py` with a disposable DSN.
- Local HTTPS boundary: **PASS** through a disposable loopback TLS
  terminator; certificate validation and protected-request authentication were
  exercised. Docker deployment: **NOT VERIFIED** because its daemon was
  unavailable.

## Not qualified

Production Git repositories, hosted public transport, Keychain access with real
credentials, external identity providers, payment processors, deployment, and
launcher activation were not exercised.

## Evidence boundary

These results are local unit/integration evidence only. They do not imply
host, deployment, environment, or fleet qualification.
