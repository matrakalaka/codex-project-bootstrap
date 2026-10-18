# AgentTerm Phase 0 security review

This is an adversarial engineering review, not independent human approval.

## Findings and corrections

### High — trust ownership was not initially bound to an envelope

Original behavior: `SignedEnvelope.verify` checked `key_id`, status, and
validity but did not require `TrustRecord.owner == envelope.principal`.

Risk: a trusted key record could be substituted across principals if a later
trust store admitted an incorrect owner binding.

Correction: verification now rejects misbound trust records. Regression
coverage is in `tests/test_phase0_security.py`.

### Medium — algorithm and malformed encoding handling was permissive

Original behavior: any algorithm label was accepted and malformed hex could
escape as a raw `ValueError`.

Correction: only `Ed25519` and the explicitly opaque ciphertext contract are
accepted; malformed key/signature encodings fail as `SecurityError`.

### Medium — replay and content verification were only described

Original behavior: the envelope carried sequence/content metadata but had no
verification API for plaintext or process-local replay state.

Correction: `verify_content` and `ReplayGuard` reject digest mismatch,
duplicate object IDs/digests, and non-increasing per-device project sequence.
Durable multi-device cursor/recovery remains Phase 3 scope.

### Low — SQLite resource hygiene

Original behavior: `cmd_doctor` leaked its in-memory FTS5 probe; short-lived
ledger users could leave connections to garbage collection.

Correction: the probe is explicitly closed, `Ledger` supports `with` and
defensive finalization, and the strict ResourceWarning suite is clean.

## Review matrix

| Area | Implemented protection | Remaining limitation |
|---|---|---|
| Ed25519 | Canonical JSON, domain separation, `s < L`, malformed rejection, exact algorithm labels | Pure-Python implementation needs independent cryptographic review; subgroup/vector breadth must be expanded before production |
| Key management | 32-byte seed validation, no seed in envelope, owner-bound active/validity checks | `MemoryKeyStore` is test-only; no OS keychain, durable trust registry, rotation workflow, or recovery |
| Authorization | Exact principal/operation/resource grants; missing actor and unknown grants deny | No server authority, session/token validation, tenant service, or membership-to-grant binding |
| Audit | Canonical receipt digest, predecessor field, explicit digest/predecessor verification | No durable receipt store, signed receipts, duplicate index, or independent ledger anchoring |
| Replay | Process-local object and per-device sequence guard | No durable sync cursor, vector clock, crash recovery, or cross-device convergence |
| Envelope | Schema/version/project/expiry/key/owner/algorithm checks and content digest | `ciphertext` remains opaque; no AEAD implementation, nonce policy, key wrapping, or decryption |
| Worktree | Data-only lease contract and repository identity equality | No path canonicalization, symlink defense, lock, create/merge/discard, cleanup, or process isolation |

## Attack cases exercised

Tests cover RFC-derived public-key/signature behavior, tampering, wrong
content, wrong project, wrong owner, revoked key, unknown algorithm, malformed
signature, duplicate replay, sequence rollback, canonical receipt mismatch,
deny-by-default authorization, cross-project worktree/sync rejection, inactive
membership, and revoked entitlement.

Oversized input remains bounded by the underlying hash/input APIs but has no
explicit application size limit yet. This is a Phase 1/3 API-boundary
requirement, not silently treated as solved.

## Residual security requirements

Independent review must validate Ed25519 implementation correctness and decide
whether to replace it with a maintained cryptographic library. Before any
operational sync or team service, review must approve OS-backed private-key
storage, trust-store integrity, AEAD, key rotation/revocation/recovery,
durable replay state, server authorization, and tenant isolation.
