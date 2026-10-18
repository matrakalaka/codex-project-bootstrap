# AgentTerm production-readiness audit

Date: 2026-10-18
Scope: source and local synthetic qualification in the Phase 1 worktree.

## Findings

| Area | Classification | Evidence | Action/status |
|---|---|---|---|
| Worktree lifecycle | IMPLEMENTED AND VERIFIED | `worktree.py`, `test_worktree_phase1.py` | Synthetic create/status/preview/archive/merge/discard/recovery and locking tested. |
| Production Git mutation | SECURITY BLOCKER / REQUIRES HUMAN APPROVAL | `ProductionGitAdapter` | Explicitly fails closed; no activation switch exists. |
| Metadata integrity | IMPLEMENTED AND VERIFIED | HMAC-authenticated atomic JSON records and tamper tests | Local manager key only. |
| Ed25519/AES-GCM | IMPLEMENTED BUT INCOMPLETE | `platform.py`, `test_platform.py` | Maintained `cryptography` provider used; independent review still required. |
| Private-key storage | IMPLEMENTED BUT INCOMPLETE | `MacOSKeychainStorage`, `FileKeyStorage` | Keychain adapter is explicit; file adapter is development-only. |
| Encrypted sync | IMPLEMENTED BUT INCOMPLETE | `LocalSyncServer`, `OfflineQueue`, loopback/migration tests | Local opaque service and loopback transport exist; normal-host transport and remote security remain unqualified. |
| Team authorization | IMPLEMENTED BUT INCOMPLETE | `TeamService`, cross-tenant/revocation tests | In-memory local service; no hosted identity authority. |
| Entitlements | IMPLEMENTED BUT INCOMPLETE | `EntitlementService` tests | Local mock billing state; no processor or durable billing ledger. |
| CLI | IMPLEMENTED AND VERIFIED | `platform-demo`, CLI smoke | Demonstration is local-only and reports real workflow results. |
| AF_UNIX managed PTY | BLOCKED | root regression | Four tests skipped because sandbox denies AF_UNIX bind. |
| Production service/deployment | EXTERNAL DEPENDENCY | no service provisioned | Deliberately not provisioned. |

## Source-level corrections made

The audit added a non-overwriting atomic development key store, explicit
Keychain adapter contract, sync payload/version limits, per-device replay
sequences, durable offline retry queue, billing-event idempotency, real
disposable worktree execution in the demo, and interrupted/unknown recovery
evidence.

## Host-discovered SQLite defect and correction

Normal macOS qualification exposed `SQLite objects created in a thread can
only be used in that same thread` during authenticated loopback upload. The
root cause was `LocalSyncServer` storing one `self.db` connection created by
the caller thread while `ThreadingHTTPServer` executed upload/download
handlers on worker threads.

`LocalSyncServer` now creates a short-lived connection per operation, enables
WAL and a busy timeout on each connection, uses `BEGIN IMMEDIATE` with
rollback-on-error for uploads and cursors, and closes every connection in a
context manager. `OfflineQueue` uses the same ownership model. The server no
longer exposes or shares a persistent SQLite connection. Rate-limit state is
protected separately by a lock.

The fix preserves schema migration, idempotency, replay protection, cursor
monotonicity, tenant/device checks, and corruption quarantine.

## Conclusion

The local implementation is suitable for independent review. It is not
production activated and must not be described as a hosted synchronization,
team, billing, or production Git service.
