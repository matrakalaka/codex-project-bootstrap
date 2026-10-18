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
