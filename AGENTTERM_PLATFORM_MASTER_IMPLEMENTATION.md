# AgentTerm platform master implementation

Status: local development implementation qualified; production activation is
disabled pending independent security and host review.

## Current checkpoint

Branch `feature/agentterm-worktree-phase1`, starting checkpoint
`12e2ea0720792422faa0c63e41a8c9a69c11399f`, with local platform work continuing
in the same worktree. Protected repositories and production services remain
untouched.

## Implemented locally

The platform now has a synthetic worktree engine and local platform services:

- worktree lifecycle, authenticated metadata, approval binding, recovery, and
  synthetic Git mutation;
- maintained `cryptography` Ed25519 and AES-GCM provider encapsulation;
- device identities, trust registry, rotation/revocation, signed envelopes;
- opaque SQLite local sync service, encrypted payloads, cursors, idempotency,
  replay rejection, and optimistic conflict detection;
- tenant-scoped organizations/workspaces, owner/editor/viewer roles, one-time
  invitations, server-side authorization, and revocation;
- deterministic local plans, subscription state, usage metering, limits, and
  revocation;
- `agentterm platform-demo` end-to-end local exercise.

## Explicitly incomplete or disabled

Hosted transport, server authentication, production keychain/KMS adapters,
device pairing UX, production worktree mutation, SSO, live billing, payment
processing, retention enforcement, SIEM export, and deployment are not active.
The local file key store is marked development-only. The service stores opaque
ciphertext, but this local process is not a production trust boundary.

## Promotion gates

Independent cryptographic/security review, OS-backed key storage, authenticated
transport and service isolation, host-qualified AF_UNIX evidence, production
worktree mutation approval, operational recovery policy, and external provider
credentials are required before activation. Passing local tests does not grant
those approvals.

## Qualification checkpoint

At the current hardening checkpoint:

- AgentTerm suite: **117 passed**, **1 skipped** (sandbox-denied loopback bind), including Phase 0 security, Phase 1
  worktree, and platform adversarial tests;
- strict `ResourceWarning`: **117 passed**, **1 skipped**;
- Bootstrap/security/continuity regression: **101 passed**, **4 skipped**;
  every skip is an AF_UNIX bind denied by the host sandbox and remains
  unqualified;
- compilation and `git diff --check`: **PASS**;
- protected Phase 0 and Bootstrap worktrees: unchanged by this mission.
