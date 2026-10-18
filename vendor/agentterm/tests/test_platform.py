import json
import sqlite3
from dataclasses import replace

import pytest

from agentterm.platform import (AuthorizationDenied, ConflictError, CryptoProvider, EntitlementService,
                                LocalSyncServer, PlatformError, SyncClient, TeamService, TrustRegistry,
                                create_device, integrated_local_flow)


def setup_platform(tmp_path):
    registry = TrustRegistry()
    alice, alice_private = create_device("org", "workspace", "project", "alice", registry=registry)
    bob, bob_private = create_device("org", "workspace", "project", "bob", registry=registry)
    server = LocalSyncServer(tmp_path / "sync.db", registry=registry)
    key = b"k" * 32
    return registry, alice, alice_private, bob, bob_private, server, key


def test_aead_sync_is_opaque_signed_and_idempotent(tmp_path):
    registry, alice, private, bob, _, server, key = setup_platform(tmp_path)
    client = SyncClient(alice, private, key, server)
    envelope = client.publish("o1", b"secret plaintext", sequence=1)
    assert b"secret plaintext" not in (tmp_path / "sync.db").read_bytes()
    assert SyncClient(bob, private, key, server).consume(server.pull(bob, "project")[0]) == b"secret plaintext"
    server.upload(envelope)
    assert len(server.pull(bob, "project")) == 1
    registry.revoke(alice.key_id)
    with pytest.raises(PlatformError): client.publish("o2", b"revoked", sequence=2)
    server.close()


def test_sync_conflict_and_cursor_rollback_are_fail_closed(tmp_path):
    registry, alice, alice_private, bob, bob_private, server, key = setup_platform(tmp_path)
    one = SyncClient(alice, alice_private, key, server); two = SyncClient(bob, bob_private, key, server)
    first = one.publish("shared", b"one", sequence=1)
    second = two.publish("shared", b"two", sequence=2, base_digest=first.digest())
    with pytest.raises(ConflictError): one.publish("shared", b"stale", sequence=3, base_digest=first.digest())
    server.advance_cursor(bob, "project", 2)
    with pytest.raises(PlatformError): server.advance_cursor(bob, "project", 1)
    assert two.consume(second) == b"two"
    server.close()


def test_team_tenant_role_invitation_and_revocation():
    registry = TrustRegistry(); alice, _ = create_device("org", "ws", "p", "alice", registry=registry); bob, _ = create_device("org", "ws", "p", "bob", registry=registry)
    team = TeamService(); team.create_workspace("org", "ws", alice.principal)
    token = team.invite(alice.principal, "bob", "viewer"); team.accept(token, bob.principal)
    team.authorize(bob.principal, "read")
    with pytest.raises(AuthorizationDenied): team.authorize(bob.principal, "write")
    team.revoke(alice.principal, "bob")
    with pytest.raises(AuthorizationDenied): team.authorize(bob.principal, "read")
    with pytest.raises(AuthorizationDenied): team.accept(token, bob.principal)


def test_entitlements_meter_limits_and_revoke():
    billing = EntitlementService(); billing.subscribe("org", "free")
    assert billing.permit("org", "sync_objects")
    for _ in range(99): assert billing.permit("org", "sync_objects")
    assert not billing.permit("org", "sync_objects")
    billing.revoke("org"); assert not billing.permit("org", "sync_objects")


def test_integrated_local_flow(tmp_path):
    result = integrated_local_flow(tmp_path)
    assert result["encrypted_sync"] and result["team_revocation"] and result["entitlement_enforced"]


def test_crypto_rejects_wrong_key_and_tampering():
    private, public = CryptoProvider.signing_key(); message = b"signed"
    signature = CryptoProvider.sign(private, message)
    assert CryptoProvider.verify(public, message, signature)
    assert not CryptoProvider.verify(public, b"tampered", signature)
    nonce, ciphertext = CryptoProvider.encrypt(b"x" * 32, b"secret", b"aad")
    with pytest.raises(PlatformError): CryptoProvider.decrypt(b"y" * 32, nonce, ciphertext, b"aad")


def test_tampered_envelope_cross_project_and_key_rotation_fail(tmp_path):
    registry, alice, private, bob, _, server, key = setup_platform(tmp_path)
    envelope = SyncClient(alice, private, key, server).publish("o1", b"x", sequence=1)
    with pytest.raises(PlatformError): server.upload(replace(envelope, ciphertext="tampered"))
    with pytest.raises(PlatformError): server.upload(replace(envelope, project_id="other-project"))
    rotated, rotated_private = registry.rotate(alice.principal, alice.key_id)
    assert rotated.predecessor == alice.key_id
    registry.revoke(rotated.key_id)
    with pytest.raises(PlatformError): registry.get(rotated.key_id, alice.principal)
    server.close()


def test_expired_plan_and_misbinding_are_denied():
    registry = TrustRegistry(); alice, _ = create_device("org", "ws", "p", "alice", registry=registry); mallory, _ = create_device("other", "ws", "p", "mallory", registry=registry)
    team = TeamService(); team.create_workspace("org", "ws", alice.principal)
    with pytest.raises(AuthorizationDenied): team.invite(mallory.principal, "x", "viewer")
    with pytest.raises(AuthorizationDenied): team.accept("forged-token", mallory.principal)
    billing = EntitlementService(); billing.subscribe("org", "pro", expires_at="2000-01-01T00:00:00Z")
    assert not billing.permit("org", "sync_objects")
