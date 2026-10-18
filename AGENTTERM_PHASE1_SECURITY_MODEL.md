# AgentTerm Phase 1 security model

## Threat model

The engine treats the source checkout as user-owned and potentially dirty,
worktree metadata as tamperable, concurrent allocators as hostile to one
another, and directories under the application root as possibly unknown. It
does not claim to defend against a process with unrestricted host privileges or
a compromised Python runtime.

## Controls

- Deny-by-default operation authorization uses Phase 0 exact principal,
  operation, and resource grants.
- Source identity binds canonical remote/local identity and source HEAD.
- Managed paths must resolve beneath the application root and cannot be
  protected checkouts or symlink substitutions.
- Allocation and mutation are serialized by an inter-process lock; IDs are
  collision-resistant and branch names are unique.
- Metadata has authenticated canonical JSON and atomic writes.
- Merge/discard are separate explicit approval operations and cannot reuse an
  approval or silently accept changed repository identity/source HEAD.
- Recovery reports missing or unknown objects and never deletes unknown or
  dirty content.
- Process launch uses the assigned worktree as cwd, strips caller PWD values,
  and supplies only a bounded environment baseline.
- Audit provenance is redacted through the existing Phase 0 redactor.

## Synthetic mutation rule

Only `SyntheticGitAdapter` can call `git worktree add`, `git merge`, or
`git worktree remove`. It verifies the source is a Git fixture and confines
source access to that fixture. Production behavior is disabled by the default
adapter and raises an error before mutation.

## Residual risks and gates

The local metadata key is an application-local secret, not OS-backed key
storage. Lease expiry is represented but not scheduled. Merge conflict
handling is fail-closed at the Git command boundary, and no automatic recovery
of a partially completed Git command is attempted. Independent security review
must approve any production adapter, host-specific locking assumptions,
credential/environment policy, and operational cleanup policy.
