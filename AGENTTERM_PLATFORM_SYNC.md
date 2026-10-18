# Local synchronization protocol

Devices publish signed `agentterm.sync.v1` envelopes. Payloads are encrypted
with AES-GCM using project key material held by clients; the local SQLite
server stores only nonce, ciphertext, metadata, and signature. AAD binds the
project, object ID, and sequence. The server verifies sender ownership and
trust status before storing an envelope.

Per-device sequences reject rollback/replay. Repeating the same exact envelope
is idempotent. A changed object must identify the latest envelope digest as its
base; otherwise `ConflictError` requires explicit resolution. Cursors are
durable and cannot move backwards.

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
