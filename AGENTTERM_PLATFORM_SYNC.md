# Local synchronization protocol

Devices publish signed `agentterm.sync.v1` envelopes. Payloads are encrypted
with AES-GCM using project key material held by clients; the local SQLite
server stores only nonce, ciphertext, metadata, and signature. AAD binds the
project, object ID, and sequence. The server verifies sender ownership and
trust status before storing an envelope.

Per-device sequences use a durable bounded out-of-order replay window. Arrival
order is not a sequencing contract: concurrent valid publications may arrive
in any order within the window. Repeating the same exact envelope is
idempotent; reusing a sequence with different content raises
`SequenceConflict`; a sequence below the durable window raises
`StaleEnvelope`. A changed object must identify the latest envelope digest as
its base; otherwise `ConflictError` requires explicit resolution. Cursors are
durable and cannot move backwards.

The window preserves offline/concurrent publication without accepting
unbounded stale replay. The sequence table is unique per device/project and is
transactionally updated with the envelope row, so the rule survives restart.

This model fixes the host-discovered failure where concurrent sequences 2–5
arrived in a different order and the server incorrectly rejected any sequence
below the current maximum as non-increasing. The old rule conflated arrival
ordering with replay. The corrected rule distinguishes exact duplicate
envelopes, altered sequence reuse (`SequenceConflict`), and outside-window
stale envelopes (`StaleEnvelope`).

This is a local development transport abstraction. It does not provide TLS,
remote authentication, multi-process service hardening, key distribution, or
production offline queue delivery.

`LoopbackSyncService` provides a bounded bearer-authenticated HTTP transport on
`127.0.0.1` with an ephemeral port. It is suitable only for development
qualification; sandbox bind restrictions may prevent its test from running.
It must not be exposed to a LAN or treated as production TLS.

SQLite ownership: `LocalSyncServer` and `OfflineQueue` do not share a
connection across requests or threads. Each operation opens and closes its
own connection, with WAL, busy timeout, and explicit write transactions.
