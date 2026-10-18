# AgentTerm production qualification report

## Local results

- AgentTerm tests: **111 PASS**.
- Strict `ResourceWarning`: **111 PASS**.
- Bootstrap/security/continuity regression: **101 PASS**, **4 SKIP**.
- AF_UNIX tests: **4 SKIP / BLOCKED**, each reports sandbox-denied bind.
- Compilation: **PASS**.
- `git diff --check`: **PASS**.
- CLI integration: `platform-demo` completed signed encrypted sync, conflict
  detection, team revocation, entitlement gating, real disposable worktree
  merge, and blocked unknown recovery.

## Not qualified

Production Git repositories, hosted transport, Keychain access with real
credentials, external identity providers, payment processors, deployment,
launcher activation, and normal-host AF_UNIX behavior were not exercised.

## Evidence boundary

These results are local unit/integration evidence only. They do not imply
host, deployment, environment, or fleet qualification.
