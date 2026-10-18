# Platform recovery

Worktree recovery remains conservative: missing records become orphaned,
unknown directories are reported as blocked, and no unknown or dirty content
is automatically removed. Metadata writes use authenticated canonical JSON and
atomic replacement.

Sync recovery uses durable per-device cursors, monotonic sequences, idempotent
retries, and explicit base-digest conflicts. A client must resolve a conflict
and publish a new envelope; the server never silently chooses a winner.

Crash injection around every Git subprocess and a host-qualified operational
recovery exercise remain required before production activation.
