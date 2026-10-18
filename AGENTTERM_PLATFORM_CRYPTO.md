# Platform cryptography

`agentterm.platform.CryptoProvider` uses the maintained `cryptography`
provider for Ed25519 signatures and AES-GCM authenticated encryption. There is
no insecure fallback: missing provider support raises `CryptoUnavailable`.

Signed sync envelopes bind schema, project, object, sender device, sequence,
base digest, ciphertext metadata, key ID, and creation time. Trust records bind
public keys to principals and reject unknown, revoked, or misbound keys.

`FileKeyStorage` is only a local development adapter (`production_ready =
False`). A production adapter must use macOS Keychain or an approved KMS,
support rotation/recovery, and keep private key material out of logs and
exports. Existing HMAC bundle files remain supported by the legacy bundle API;
they are integrity/authentication compatibility, not Ed25519 signatures or
end-to-end encryption.
