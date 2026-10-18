# AgentTerm independent security review packet

## Trust boundaries

1. User-owned source repository: never mutated by the default adapter.
2. Application worktree root: manager-owned paths, authenticated metadata, and
   lock-protected lifecycle records.
3. Local sync service: stores signed ciphertext only; clients hold project key
   material.
4. Team service: operation-boundary role checks over organization/workspace
   membership.
5. Entitlement service: feature limits only; it cannot grant authorization.
6. External production boundary: not implemented or activated.

## Security properties reviewed

Canonical signed envelopes, Ed25519 key IDs and owner binding, AES-GCM AAD,
nonce generation, algorithm/version checks, replay sequences, durable cursor
monotonicity, opaque server storage, exact role authorization, one-time
invitation binding, revocation, worktree path/symlink protection, approval
binding, atomic metadata, unknown-content preservation, and redacted audit
provenance are covered by source and adversarial tests.

## Review questions requiring human decision

- Is `cryptography` provider version and Ed25519 usage independently accepted?
- What OS keychain/KMS and recovery policy is approved?
- What authenticated transport and server isolation are required?
- Is production Git mutation permitted, and under what host qualification?
- What retention, tenant, billing, and incident-response controls are required?

Codex self-review and local tests do not constitute independent approval.

## Corrective security evidence

The host-discovered cross-thread SQLite defect was corrected by removing the
shared server connection. Upload, pull, cursor, migration, and queue operations
now own short-lived connections and close them deterministically. Concurrent
direct storage tests pass; the actual HTTP-thread test remains host-dependent
and must be rerun on normal macOS.

The subsequent concurrent-sequence defect was corrected without removing replay
checks: the durable sequence table remains unique, exact retry is idempotent,
altered reuse is rejected, and only unseen sequences inside the bounded replay
window are accepted out of order.

The local sync read path was also hardened: a pull now requires an active
trusted key whose principal, device ID, and public key match the presented
device. HTTP callers receive classified authorization, conflict/replay, size,
and malformed-request responses. The local test suite covers revoked and
forged readers; normal-host HTTP qualification remains required.

Synthetic provider evidence now includes PKCE authorization-code exchange,
Ed25519 token verification with key rotation, tenant claim binding, signed
billing events, timestamp/replay rejection, ordered subscription transitions,
and failed-payment revocation. These are local protocol tests, not approval of
any external identity or payment provider.
