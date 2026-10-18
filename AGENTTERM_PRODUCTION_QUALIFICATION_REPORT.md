# AgentTerm production qualification report

## Local results

- AgentTerm tests: **118 PASS**, **1 SKIP** for sandbox-denied loopback bind.
- Strict `ResourceWarning`: **118 PASS**, **1 SKIP** for sandbox-denied loopback bind.
- Bootstrap/security/continuity regression: **101 PASS**, **4 SKIP**.
- AF_UNIX tests: **4 SKIP / BLOCKED**, each reports sandbox-denied bind.
- Loopback HTTP transport: **1 SKIP / BLOCKED**, sandbox denies loopback bind.

## Host defect record

Normal macOS qualification previously produced 24 passed and 1 failed. The
failure was the real threaded loopback upload path: a SQLite connection owned
by the construction thread was reused by an HTTP worker thread. The corrected
implementation uses per-operation connections and explicit transactions. The
loopback test must be rerun on that normal host after this commit.

The follow-up host failure was caused by strict highest-sequence arrival
enforcement. Concurrent valid publications from one device were not replay,
but their HTTP arrival order was nondeterministic. The fix uses bounded
out-of-order acceptance with durable per-device uniqueness and explicit
`SequenceConflict`/`StaleEnvelope` classifications. The original host command
must be rerun after this commit.
- Compilation: **PASS**.
- `git diff --check`: **PASS**.
- CLI integration: `platform-demo` completed signed encrypted sync, conflict
  detection, team revocation, entitlement gating, real disposable worktree
  merge, backup, offline retry, restart/idempotent replay, health inspection,
  and blocked unknown recovery. `platform-health` reported SQLite integrity
  `ok`, schema version `2`, and two stored objects.
- Packaging: **PASS**; a no-dependency `agentterm-0.1.0-py3-none-any.whl`
  was built in the isolated environment.

## Not qualified

Production Git repositories, hosted transport, Keychain access with real
credentials, external identity providers, payment processors, deployment,
launcher activation, and normal-host AF_UNIX behavior were not exercised.

## Evidence boundary

These results are local unit/integration evidence only. They do not imply
host, deployment, environment, or fleet qualification.
