from agentterm.authorization import AuditReceipt, Grant, authorize
from agentterm.phase0_contracts import Entitlement, SyncObject, TeamMembership, WorktreeLease
from agentterm.security import (MemoryKeyStore, Principal, ReplayGuard, SecurityError,
                                SignedEnvelope, TrustRecord, public_key, sign, verify)


def test_ed25519_rfc_key_derivation_and_domain_separated_vector():
    seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    key = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    # Public-key derivation matches RFC 8032. Signatures intentionally include
    # AgentTerm's domain separator and therefore differ from the raw RFC vector.
    signature = bytes.fromhex("849ff4a04ee8f05e3f391393c7470b7b8de16933db8cb1cdcb240c23effadbd8" "8618bf499086834bf89dd5d95235cebd2756153eefd02d20e654b1e9b1842908")
    assert public_key(seed) == key
    assert sign(seed, b"") == signature
    assert verify(key, b"", signature)
    assert not verify(key, b"tampered", signature)


def test_signed_envelope_binds_project_sequence_and_expiry():
    seed = bytes(range(32)); principal = Principal("org", "ws", "project", "device", "user")
    envelope = SignedEnvelope.create(object_id="obj", object_type="ledger.event", principal=principal,
                                     key_id="device-key-1", seed=seed, content=b"hello", sequence=4,
                                     created_at="2026-01-01T00:00:00Z", expires_at="2030-01-01T00:00:00Z")
    trust = TrustRecord("device-key-1", principal, public_key(seed).hex(), not_before="2025-01-01T00:00:00Z")
    envelope.verify(trust, at="2026-02-01T00:00:00Z", expected_project="project")
    envelope.verify_content(b"hello")
    try: envelope.verify_content(b"changed"); assert False
    except SecurityError: pass
    try:
        envelope.verify(trust, at="2026-02-01T00:00:00Z", expected_project="other")
        assert False
    except SecurityError: pass
    revoked = TrustRecord("device-key-1", principal, public_key(seed).hex(), status="revoked")
    try:
        envelope.verify(revoked, at="2026-02-01T00:00:00Z")
        assert False
    except SecurityError: pass
    wrong_owner = TrustRecord("device-key-1", Principal("other", "ws", "project", "device", "user"), public_key(seed).hex())
    try: envelope.verify(wrong_owner); assert False
    except SecurityError: pass
    unknown_algorithm = SignedEnvelope(**{**envelope.__dict__, "algorithm": "none"})
    try: unknown_algorithm.verify(trust); assert False
    except SecurityError: pass
    malformed = SignedEnvelope(**{**envelope.__dict__, "signature": "not-hex"})
    try: malformed.verify(trust); assert False
    except SecurityError: pass


def test_replay_guard_rejects_duplicates_and_old_sequences():
    seed = bytes(range(32)); p = Principal("o", "w", "p", "d")
    e1 = SignedEnvelope.create(object_id="1", object_type="x", principal=p, key_id="k", seed=seed, content=b"1", sequence=1)
    e0 = SignedEnvelope.create(object_id="0", object_type="x", principal=p, key_id="k", seed=seed, content=b"0", sequence=0)
    guard = ReplayGuard(); guard.accept(e1)
    for item in (e1, e0):
        try: guard.accept(item); assert False
        except SecurityError: pass


def test_keystore_never_exposes_seed_in_contract():
    store = MemoryKeyStore(); seed = bytes(range(32)); store.put("k", seed)
    assert store.get_private_seed("k") == seed
    assert "seed" not in str(SignedEnvelope.create(object_id="o", object_type="t", principal=Principal("o", "w", "p", "d"), key_id="k", seed=seed, content=b"x", sequence=0).unsigned())


def test_authorization_is_deny_by_default_and_receipt_is_provenance():
    actor = Principal("o", "w", "p", "d", "u")
    denied = authorize(actor, "write", "memory/1", [])
    assert not denied.allowed
    allowed = authorize(actor, "write", "memory/1", [Grant(actor, "write", "memory/1", grant_id="g1")])
    assert allowed.allowed and allowed.grant_id == "g1"
    receipt = AuditReceipt("r", "req", actor, "write", "memory/1", allowed, "accepted", {"source": "local"})
    assert receipt.digest().startswith("sha256:") and receipt.as_dict()["decision"] is True
    receipt.verify(receipt.digest(), previous_digest=None)
    try: receipt.verify("sha256:" + "0" * 64); assert False
    except ValueError: pass


def test_phase0_boundary_contracts_fail_closed():
    worktree = WorktreeLease("w", "repo-a", "a" * 40, "/tmp/w", "agent/w", "d", "task")
    worktree.validate("repo-a")
    try: worktree.validate("repo-b"); assert False
    except ValueError: pass
    sync = SyncObject("o", "p", 0, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
    sync.validate("p")
    assert TeamMembership("o", "w", "p", "u", "viewer").can("read")
    assert not TeamMembership("o", "w", "p", "u", "unknown").can("read")
    assert Entitlement("a", "pro", "active", "event").permits("sync")
    assert not Entitlement("a", "pro", "revoked", "event").permits("sync")
