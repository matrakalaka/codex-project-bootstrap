# AgentTerm Phase 1 worktree architecture

## Scope and boundary

Phase 1 implements an application-managed lifecycle for isolated Git
worktrees, but only the `SyntheticGitAdapter` is permitted to mutate Git. It
accepts a repository explicitly identified as a disposable fixture. The
default `ProductionGitAdapter` rejects create, merge, and discard. No user
checkout, deployment repository, device, launcher, or production service is
opened by this implementation.

## Components

`agentterm.worktree` contains:

- `RepositoryIdentity`, derived from the resolved repository, canonical remote
  identity, and source HEAD; path strings alone are never the repository key.
- `WorktreeManager`, which owns application-root validation, authenticated
  JSON metadata, atomic replacement, an inter-process `fcntl` lock, state
  transitions, approval binding, audit receipts, and recovery enumeration.
- `SyntheticGitAdapter`, which invokes only bounded local Git commands inside a
  caller-provided disposable fixture and creates a detached task branch.
- `ProductionGitAdapter`, a fail-closed mutation boundary.
- `run_in_worktree`, which validates state and launches with the assigned
  directory as cwd and a minimal environment.

## Lifecycle

`ALLOCATED -> ACTIVE -> READY_FOR_REVIEW -> MERGED` is the successful path.
`ACTIVE` or `READY_FOR_REVIEW` can be explicitly discarded. Missing paths,
interrupted operations, or contradictory evidence are reported as
`ORPHANED`/`BLOCKED`; unknown directories are never deleted. `MERGED`,
`DISCARDED`, `RECOVERED`, and `BLOCKED` are terminal in this implementation.

Merge and discard approvals bind operation ID, actor, worktree ID, canonical
repository identity, source HEAD, target ref, and review digest. Approval IDs
are one-use and replay is rejected.

## Persistence and provenance

Each record is serialized under the application state root using a temporary
file plus `os.replace`. A manager-local 32-byte key authenticates the
canonical metadata; tampering fails closed. Optional Phase 0 `Ledger` use
records redacted operation receipts. This is local provenance, not a remote
attestation service.

## Deliberate non-features

There is no production Git mutation, automatic cleanup, guessed ownership,
network authorization, OS keychain integration, lease scheduler, or automatic
conflict resolver. Those remain approval gates for a later operational phase.
