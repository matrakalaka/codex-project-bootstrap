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
