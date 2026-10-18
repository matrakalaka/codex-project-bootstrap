import json
import sqlite3
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import pytest

from agentterm.platform import (AuthorizationDenied, ConflictError, CryptoProvider, EntitlementService,
                                FileKeyStorage, LocalSyncServer, LoopbackSyncService, LoopbackSyncTransport, OfflineQueue, PlatformError, SequenceConflict, StaleEnvelope, SyncClient, TeamService, TrustRegistry,
                                _b64, create_device, integrated_local_flow)


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


def test_pull_requires_active_bound_device(tmp_path):
    registry, alice, private, bob, _, server, key = setup_platform(tmp_path)
    SyncClient(alice, private, key, server).publish("read", b"data", sequence=1)
    assert len(server.pull(bob, "project")) == 1
    registry.revoke(bob.key_id)
    with pytest.raises(PlatformError): server.pull(bob, "project")
    forged = replace(alice, device_id="not-alice")
    with pytest.raises(AuthorizationDenied): server.pull(forged, "project")
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
    assert result["conflict_detected"] and result["worktree_merged"] and result["recovery_blocked_unknown"]
    assert result["backup_created"] and result["queue_recovered"] and result["restart_replay_idempotent"]


def test_health_backup_and_corruption_signal(tmp_path):
    registry, alice, private, _, _, server, key = setup_platform(tmp_path)
    SyncClient(alice, private, key, server).publish("health", b"data", sequence=1)
    assert server.health()["ok"] and server.health()["objects"] == 1
    backup = server.backup(tmp_path / "backup.db"); server.close()
    restored = LocalSyncServer(backup, registry=registry)
    assert restored.health()["ok"] and restored.health()["objects"] == 1
    restored.close()


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


def test_key_store_preserves_keys_and_offline_queue_retries(tmp_path):
    private, _ = CryptoProvider.signing_key(); other, _ = CryptoProvider.signing_key()
    keys = FileKeyStorage(tmp_path / "keys.json"); keys.put("one", private); keys.put("two", other)
    assert keys.get("one") == private and keys.get("two") == other
    registry, alice, alice_private, _, _, server, key = setup_platform(tmp_path)
    envelope = SyncClient(alice, alice_private, key, server).publish("queued", b"data", sequence=1)
    queue = OfflineQueue(tmp_path / "queue.db"); queue.enqueue(envelope)
    assert queue.flush(type("Failing", (), {"upload": lambda self, item: (_ for _ in ()).throw(PlatformError("offline"))})(), now=0) == (0, 1)
    assert queue.flush(server, now=2) == (1, 0)
    queue.close(); server.close()


def test_billing_event_is_idempotent_and_size_limits_apply(tmp_path):
    billing = EntitlementService(); assert billing.apply_billing_event("evt-1", "org", "subscription.updated", plan="pro")
    assert not billing.apply_billing_event("evt-1", "org", "subscription.updated", plan="free")
    assert billing.status("org")["subscription"]["plan"] == "pro"
    registry, alice, private, _, _, server, key = setup_platform(tmp_path)
    with pytest.raises(PlatformError): SyncClient(alice, private, key, server).publish("large", b"x" * (LocalSyncServer.max_envelope_bytes + 1), sequence=1)
    server.close()


def test_loopback_transport_is_authenticated_and_bounded(tmp_path):
    registry, alice, private, bob, _, server, key = setup_platform(tmp_path)
    try:
        service = LoopbackSyncService(server); service.start()
    except PermissionError:
        server.close(); pytest.skip("host sandbox denies loopback bind; transport remains host-unqualified")
    try:
        transport = LoopbackSyncTransport(service); client = SyncClient(alice, private, key, transport)
        envelope = client.publish("http", b"loopback", sequence=1)
        assert SyncClient(bob, private, key, server).consume(transport.pull(bob, "project")[0]) == b"loopback"
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda sequence: client.publish("parallel-" + str(sequence), b"parallel", sequence=sequence), range(2, 6)))
        with ThreadPoolExecutor(max_workers=4) as pool:
            pulls = list(pool.map(lambda _: len(transport.pull(bob, "project")), range(4)))
        assert pulls == [5, 5, 5, 5]
        service.token = "wrong"
        with pytest.raises(PlatformError): transport.upload(envelope)
    finally:
        service.close(); server.close()


def test_per_operation_connections_support_concurrent_storage_access(tmp_path):
    registry, _, _, bob, _, server, key = setup_platform(tmp_path)
    devices = [create_device("org", "workspace", "project", f"sender-{index}", registry=registry) for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda item: SyncClient(item[0], item[1], key, server).publish("direct-" + item[0].principal.user_id, b"data", sequence=1), devices))
    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(pool.map(lambda _: len(server.pull(bob, "project")), range(8)))
    assert counts == [8] * 8
    server.close()
    with pytest.raises(PlatformError):
        with server.connection():
            pass


def test_bounded_out_of_order_arrival_and_sequence_classification(tmp_path):
    registry, alice, private, _, _, server, key = setup_platform(tmp_path)
    class Recorder:
        def __init__(self): self.items = []
        def upload(self, item): self.items.append(item)
    recorder = Recorder(); client = SyncClient(alice, private, key, recorder)
    envelopes = [client.publish("ordered-" + str(sequence), b"v" + str(sequence).encode(), sequence=sequence) for sequence in range(1, 6)]
    for envelope in [envelopes[0], envelopes[4], envelopes[1], envelopes[3], envelopes[2]]: server.upload(envelope)
    server.close()
    window_root = tmp_path / "window"; window_root.mkdir()
    registry, alice, private, _, _, server, key = setup_platform(window_root)
    server.replay_window = 2
    recorder = Recorder(); client = SyncClient(alice, private, key, recorder)
    envelopes = [client.publish("window-" + str(sequence), b"v" + str(sequence).encode(), sequence=sequence) for sequence in range(1, 5)]
    server.upload(envelopes[0]); server.upload(envelopes[3])
    with pytest.raises(StaleEnvelope): server.upload(envelopes[1])
    altered_unsigned = replace(envelopes[3], ciphertext="altered", signature="")
    altered = replace(altered_unsigned, signature=_b64(CryptoProvider.sign(private, altered_unsigned.signing_bytes())))
    with pytest.raises(SequenceConflict): server.upload(altered)
    server.close()


def test_replay_state_survives_restart_and_uncertain_retry_is_idempotent(tmp_path):
    registry, alice, private, _, _, server, key = setup_platform(tmp_path)
    class Uncertain:
        def upload(self, item):
            server.upload(item)
            raise TimeoutError("response lost after commit")
    queue = OfflineQueue(tmp_path / "retry.db"); client = SyncClient(alice, private, key, server)
    envelope = client.publish("retry", b"retry", sequence=1)
    queue.enqueue(envelope)
    assert queue.flush(Uncertain(), now=0) == (0, 1)
    assert queue.flush(server, now=2) == (1, 0)
    server.close(); restarted = LocalSyncServer(tmp_path / "sync.db", registry=registry)
    restarted.upload(envelope)
    altered = replace(envelope, ciphertext="different")
    with pytest.raises(PlatformError): restarted.upload(altered)
    queue.close(); restarted.close()


def test_corrupt_database_is_quarantined_not_deleted(tmp_path):
    path = tmp_path / "corrupt.db"; path.write_bytes(b"not sqlite")
    quarantined = LocalSyncServer.quarantine_corrupt(path)
    assert quarantined.exists() and not path.exists()


def test_sync_schema_migrates_legacy_objects_transactionally(tmp_path):
    path = tmp_path / "legacy.db"; db = sqlite3.connect(path)
    db.execute("CREATE TABLE objects (project TEXT, object_id TEXT, sequence INTEGER, envelope TEXT, digest TEXT, PRIMARY KEY(project, object_id, sequence))")
    envelope = {"object_id": "legacy", "project_id": "project", "sender_device": "device", "sequence": 1, "base_digest": None, "nonce": "n", "ciphertext": "c", "key_id": "k", "signature": "s", "created_at": "now", "schema": "agentterm.sync.v1"}
    db.execute("INSERT INTO objects VALUES(?,?,?,?,?)", ("project", "legacy", 1, json.dumps(envelope), "digest")); db.commit(); db.close()
    registry = TrustRegistry(); server = LocalSyncServer(path, registry=registry)
    with server.connection() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(objects)")}; assert "sender_device" in columns
        assert connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 1
    server.close()


def test_team_seat_entitlement_is_enforced_and_released():
    registry = TrustRegistry(); alice, _ = create_device("org", "ws", "p", "alice", registry=registry); bob, _ = create_device("org", "ws", "p", "bob", registry=registry); cara, _ = create_device("org", "ws", "p", "cara", registry=registry)
    billing = EntitlementService(); billing.subscribe("org", "free"); team = TeamService(billing); team.create_workspace("org", "ws", alice.principal)
    team.accept(team.invite(alice.principal, "bob", "viewer"), bob.principal)
    with pytest.raises(AuthorizationDenied): team.accept(team.invite(alice.principal, "cara", "viewer"), cara.principal)
    team.revoke(alice.principal, "bob")
    team.accept(team.invite(alice.principal, "cara", "viewer"), cara.principal)
