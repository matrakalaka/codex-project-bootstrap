# AgentTerm Phase 0 security and protocol contract

Phase 0 establishes additive, local contracts. It does not create a sync
service, manage Git worktrees, contact a billing provider, publish artifacts,
or change the existing ledger and bundle formats.

## Ownership

`agentterm.security` owns canonical principal identity, Ed25519 key material
contracts, trust status and validity, signature domain separation, and the
versioned `SignedEnvelope`. `agentterm.authorization` owns explicit grants,
deny-by-default decisions, and immutable audit-receipt provenance.
`phase0_contracts` owns the data-only worktree, sync, team, and entitlement
boundaries used by later phases. Existing `ledger.py` and `bundle.py` remain
owners of the legacy local ledger and HMAC bundle formats.

## Security invariants

* Unknown schema, key, project, actor, operation, resource, or entitlement is
  rejected; there is no implicit or wildcard authorization.
* Signatures cover canonical bytes with a domain-separated Ed25519 algorithm,
  object identity, project identity, sequence, expiry, content digest, and
  predecessor reference.
* A trust record must be active and within its validity interval. Revocation
  and rotation are represented by the record status and predecessor fields.
* Private seeds are accepted only through a `KeyStore` interface. The included
  `MemoryKeyStore` is a test adapter; production must supply an OS-backed
  secure-store adapter. Seeds are never serialized into envelopes or logs.
* `ciphertext` is an opaque field labelled `opaque-ciphertext-v0`. This phase
  does not claim to implement an encryption provider; a later reviewed
  provider must define authenticated encryption, nonce handling, and key
  wrapping before changing that label.

## Threat model and limitations

The local process and its key store are trusted; hostile network peers,
tampered envelopes, replay, wrong-project imports, expired/revoked keys, and
unauthorized service requests are not trusted. Availability, endpoint
compromise, secure deletion, OS keychain behavior, server tenancy, and
multi-device convergence are out of scope for Phase 0 and require later
qualification. The pure-Python Ed25519 implementation matches RFC 8032
public-key derivation and is covered by a domain-separated known-answer test.
It must receive independent cryptographic review before production use.

## Promotion boundary

Phase 1 may consume these records only after independent security review. No
contract here authorizes mutation, merge, discard, sync, billing, deployment,
or publication.
