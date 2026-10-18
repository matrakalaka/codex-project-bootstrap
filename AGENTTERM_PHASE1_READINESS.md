# AgentTerm Phase 1 readiness: managed Git worktrees

## Decision

**Conditional GO for design, API specification, and synthetic fixture work.**
**NO-GO for mutating implementation, merge/discard operations, or release
qualification until independent human security review approves Phase 0 and a
host with AF_UNIX support requalifies the managed PTY boundary.**

Phase 0 supplies records but does not isolate or mutate a Git checkout. No
Phase 1 behavior is implemented in this branch.

## Required API surface

The first implementation should expose only bounded operations:

* `worktree create` — explicit task/owner/source HEAD and approved root.
* `worktree status` and `worktree verify` — read-only identity, ownership,
  lease, branch, dirty fingerprint, and metadata integrity.
* `worktree merge --approve` — separate human approval bound to repository,
  source HEAD, worktree ID, target ref, and review digest.
* `worktree discard --approve` — explicit destructive approval; preserve
  unrelated user data and emit a receipt.
* `worktree recover` — list orphan/unknown states; never guess ownership or
  delete automatically.

## State machine

```text
ALLOCATED -> ACTIVE -> READY_FOR_REVIEW -> MERGED
     |          |              |
     v          v              v
  ORPHANED -> RECOVERED      DISCARDED
```

Unknown, contradictory, expired, or tampered metadata must transition to a
blocked/recovery state, not a successful terminal state. `MERGED` and
`DISCARDED` are terminal only after independent verification and receipt
recording.

## Safety contracts

* Repository ownership is a canonical real repository identity plus source
  HEAD/ref; path strings alone are insufficient.
* Worktree paths must be resolved beneath an application-owned root, reject
  symlink substitution and traversal, and never equal a protected checkout.
* Allocation requires an interprocess lock and collision-resistant worktree ID;
  metadata writes must be atomic and authenticated.
* The original checkout may be dirty. Create/merge/discard must preserve all
  pre-existing dirty paths and prove ownership before cleanup.
* Agent processes launch with the assigned worktree as cwd and validated
  environment/path boundaries. No operation may write the original checkout.
* Merge and discard are separate approval boundaries. Approval binds current
  repository identity, source/target heads, scope, actor, and operation ID.
* Interrupted operations remain recoverable evidence. Ambiguous ownership or
  deletion state blocks success and requires manual recovery.

## Required fixtures and qualification

Before promotion, tests must cover concurrent allocation, deep paths,
pre-existing dirty files, cross-repository rejection, branch collisions,
conflicting merge, interrupted create/merge/discard, orphan recovery,
symlink/path traversal attacks, protected repository rejection, dirty-data
preservation, lease expiry, metadata tampering, duplicate approval/replay, and
failed cleanup. At least two synthetic agents must prove they cannot write the
original checkout concurrently.

## Promotion gate

Phase 1 implementation may begin only after human review records approval of
the Phase 0 protocol, the pure-Python Ed25519 decision, and the exact mutation
boundary. Worktree qualification must remain local and synthetic until a
separate release approval authorizes any broader environment.
