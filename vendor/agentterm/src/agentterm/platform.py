"""Local AgentTerm platform services.

This module is deliberately a local development platform, not a hosted
service.  It provides real signed/AEAD-encrypted envelopes, a SQLite-backed
opaque sync service, tenant-scoped team authorization, invitations, and
deterministic local entitlements/metering.  Production activation still
requires independent review, OS-backed key storage, transport authentication,
and an operational service boundary.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from .canon import canonical_bytes, canonical_hash, utc_now
from .redact import redact_obj
from .security import Principal

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - exercised on dependency-less installs
    Ed25519PrivateKey = Ed25519PublicKey = AESGCM = None
    InvalidSignature = Exception


class PlatformError(ValueError):
    pass


class CryptoUnavailable(PlatformError):
    pass


class AuthorizationDenied(PlatformError):
    pass


class ConflictError(PlatformError):
    pass


def _require_crypto() -> None:
    if Ed25519PrivateKey is None or AESGCM is None:
        raise CryptoUnavailable("cryptography provider is required; refusing insecure downgrade")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _unb64(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:
        raise PlatformError("malformed encoded value") from exc


class CryptoProvider:
    """Encapsulation over the maintained ``cryptography`` primitives."""

    name = "cryptography.ed25519+aescgcm"

    @staticmethod
    def signing_key() -> tuple[bytes, bytes]:
        _require_crypto()
        private = Ed25519PrivateKey.generate()
        return private.private_bytes_raw(), private.public_key().public_bytes_raw()

    @staticmethod
    def sign(private: bytes, message: bytes) -> bytes:
        _require_crypto()
        return Ed25519PrivateKey.from_private_bytes(private).sign(message)

    @staticmethod
    def verify(public: bytes, message: bytes, signature: bytes) -> bool:
        _require_crypto()
        try:
            Ed25519PublicKey.from_public_bytes(public).verify(signature, message)
            return True
        except (InvalidSignature, ValueError):
            return False

    @staticmethod
    def encrypt(key: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
        _require_crypto()
        if len(key) not in {16, 24, 32}: raise PlatformError("AES key must be 128, 192, or 256 bits")
        nonce = secrets.token_bytes(12)
        return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)

    @staticmethod
    def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        _require_crypto()
        try: return AESGCM(key).decrypt(nonce, ciphertext, aad)
        except Exception as exc: raise PlatformError("ciphertext authentication failed") from exc


class MacOSKeychainStorage:
    """Keychain contract; native implementation is intentionally not activated."""
    production_ready = False
    def __init__(self, service: str = "agentterm", account: str = "default", *, runner=None):
        if runner is None: raise PlatformError("native Keychain adapter requires independent review before activation")
        self.service, self.account, self.runner = service, account, runner
    def put(self, key_id: str, private: bytes) -> None:
        raise PlatformError("Keychain adapter contract is not activated")
    def get(self, key_id: str) -> bytes:
        raise PlatformError("Keychain adapter contract is not activated")


@dataclass(frozen=True)
class TrustKey:
    key_id: str
    owner: Principal
    public_key: str
    status: str = "active"
    predecessor: str | None = None
    created_at: str = ""


class TrustRegistry:
    def __init__(self): self._keys: dict[str, TrustKey] = {}
    def add(self, key: TrustKey) -> None:
        if key.key_id in self._keys: raise PlatformError("duplicate key id")
        if len(_unb64(key.public_key)) != 32: raise PlatformError("invalid public key")
        self._keys[key.key_id] = key
    def get(self, key_id: str, owner: Principal | None = None) -> TrustKey:
        try: key = self._keys[key_id]
        except KeyError as exc: raise PlatformError("unknown signing key") from exc
        if key.status != "active" or (owner is not None and key.owner != owner): raise PlatformError("key is revoked or misbound")
        return key
    def revoke(self, key_id: str) -> None:
        key = self._keys[key_id]; self._keys[key_id] = TrustKey(**(asdict(key) | {"status": "revoked"}))
    def rotate(self, owner: Principal, predecessor: str) -> tuple[TrustKey, bytes]:
        self.get(predecessor, owner); private, public = CryptoProvider.signing_key()
        key = TrustKey("key-" + uuid.uuid4().hex, owner, _b64(public), predecessor=predecessor, created_at=utc_now())
        self.add(key); return key, private


class FileKeyStorage:
    """Local development storage; production must replace this with Keychain/KMS."""
    production_ready = False
    def __init__(self, root: Path | str): self.path = Path(root); self.path.parent.mkdir(parents=True, exist_ok=True)
    def put(self, key_id: str, private: bytes) -> None:
        values = {}
        if self.path.exists():
            try: values = json.loads(self.path.read_text())
            except json.JSONDecodeError as exc: raise PlatformError("key store is corrupt") from exc
        values[key_id] = _b64(private)
        temp = self.path.with_suffix(".tmp"); temp.write_text(json.dumps(values, sort_keys=True)); os.chmod(temp, 0o600); os.replace(temp, self.path); os.chmod(self.path, 0o600)
    def get(self, key_id: str) -> bytes:
        try: return _unb64(json.loads(self.path.read_text())[key_id])
        except (OSError, KeyError, json.JSONDecodeError) as exc: raise PlatformError("private key unavailable") from exc


@dataclass(frozen=True)
class Device:
    device_id: str
    principal: Principal
    key_id: str
    public_key: str
    status: str = "active"


def create_device(org: str, workspace: str, project: str, user: str, *, registry: TrustRegistry) -> tuple[Device, bytes]:
    private, public = CryptoProvider.signing_key()
    principal = Principal(org, workspace, project, "device-" + uuid.uuid4().hex, user)
    key = TrustKey("key-" + uuid.uuid4().hex, principal, _b64(public), created_at=utc_now()); registry.add(key)
    return Device(principal.device_id, principal, key.key_id, key.public_key), private


@dataclass(frozen=True)
class SyncEnvelope:
    object_id: str
    project_id: str
    sender_device: str
    sequence: int
    base_digest: str | None
    nonce: str
    ciphertext: str
    key_id: str
    signature: str
    created_at: str
    schema: str = "agentterm.sync.v1"

    def unsigned(self) -> dict[str, Any]: return asdict(self) | {"signature": ""}
    def signing_bytes(self) -> bytes: return canonical_bytes(self.unsigned())
    def digest(self) -> str: return canonical_hash(asdict(self))


class LocalSyncServer:
    """Opaque local service: SQLite stores ciphertext only, never plaintext."""
    protocol_version = "agentterm.sync.v1"
    max_envelope_bytes = 1 << 20
    def __init__(self, path: Path | str, *, registry: TrustRegistry):
        self.path = Path(path); self.registry = registry
        self.db = sqlite3.connect(str(self.path)); self.db.execute("CREATE TABLE IF NOT EXISTS objects (project TEXT, object_id TEXT, sender_device TEXT, sequence INTEGER, envelope TEXT, digest TEXT, PRIMARY KEY(project, object_id, sender_device, sequence))")
        self.db.execute("CREATE TABLE IF NOT EXISTS sequences (device TEXT, project TEXT, sequence INTEGER, digest TEXT, PRIMARY KEY(device, project, sequence))")
        self.db.execute("CREATE TABLE IF NOT EXISTS cursors (device TEXT, project TEXT, sequence INTEGER, PRIMARY KEY(device, project))"); self.db.commit()
    def close(self): self.db.close()
    def negotiate(self, version: str) -> bool:
        return version == self.protocol_version
    def upload(self, envelope: SyncEnvelope) -> None:
        if envelope.schema != self.protocol_version or envelope.sequence < 0: raise PlatformError("invalid sync envelope")
        if len(canonical_bytes(asdict(envelope))) > self.max_envelope_bytes: raise PlatformError("sync envelope exceeds size limit")
        device = self.registry.get(envelope.key_id)
        if device.owner.device_id != envelope.sender_device or device.owner.project_id != envelope.project_id: raise PlatformError("sender/project binding failed")
        if not CryptoProvider.verify(_unb64(device.public_key), envelope.signing_bytes(), _unb64(envelope.signature)): raise PlatformError("invalid sync signature")
        existing = self.db.execute("SELECT digest FROM objects WHERE project=? AND object_id=? AND sender_device=? AND sequence=?", (envelope.project_id, envelope.object_id, envelope.sender_device, envelope.sequence)).fetchone()
        if existing:
            if existing[0] == envelope.digest(): return
            raise ConflictError("sequence already contains a different envelope")
        latest = self.db.execute("SELECT envelope, digest FROM objects WHERE project=? AND object_id=? ORDER BY rowid DESC LIMIT 1", (envelope.project_id, envelope.object_id)).fetchone()
        if latest:
            latest_envelope = json.loads(latest[0])
            if envelope.base_digest != latest[1]:
                raise ConflictError("object has diverged; resolve against the latest envelope")
        raw = json.dumps(asdict(envelope), sort_keys=True)
        prior = self.db.execute("SELECT MAX(sequence) FROM sequences WHERE device=? AND project=?", (envelope.sender_device, envelope.project_id)).fetchone()[0]
        if prior is not None and envelope.sequence <= prior:
            raise PlatformError("replayed or non-increasing device sequence")
        self.db.execute("INSERT INTO sequences VALUES(?,?,?,?)", (envelope.sender_device, envelope.project_id, envelope.sequence, envelope.digest()))
        self.db.execute("INSERT INTO objects VALUES(?,?,?,?,?,?)", (envelope.project_id, envelope.object_id, envelope.sender_device, envelope.sequence, raw, envelope.digest()))
        self.db.commit()
    def pull(self, device: Device, project: str, after: int = 0) -> list[SyncEnvelope]:
        if device.principal.project_id != project: raise AuthorizationDenied("cross-project sync denied")
        rows = self.db.execute("SELECT envelope FROM objects WHERE project=? AND sequence>? ORDER BY sequence", (project, after)).fetchall()
        return [SyncEnvelope(**json.loads(row[0])) for row in rows]
    def advance_cursor(self, device: Device, project: str, sequence: int) -> None:
        old = self.db.execute("SELECT sequence FROM cursors WHERE device=? AND project=?", (device.device_id, project)).fetchone()
        if old and sequence < old[0]: raise PlatformError("cursor rollback")
        self.db.execute("INSERT OR REPLACE INTO cursors VALUES(?,?,?)", (device.device_id, project, sequence)); self.db.commit()


class SyncClient:
    def __init__(self, device: Device, private_key: bytes, project_key: bytes, server: LocalSyncServer):
        self.device, self.private, self.project_key, self.server = device, private_key, project_key, server
        if len(project_key) != 32: raise PlatformError("project key must be 256 bits")
    def publish(self, object_id: str, content: bytes, *, sequence: int, base_digest: str | None = None) -> SyncEnvelope:
        if len(content) > LocalSyncServer.max_envelope_bytes: raise PlatformError("sync payload exceeds size limit")
        aad = canonical_bytes({"project": self.device.principal.project_id, "object": object_id, "sequence": sequence})
        nonce, ciphertext = CryptoProvider.encrypt(self.project_key, content, aad)
        unsigned = SyncEnvelope(object_id, self.device.principal.project_id, self.device.device_id, sequence, base_digest, _b64(nonce), _b64(ciphertext), self.device.key_id, "", utc_now())
        envelope = SyncEnvelope(**(asdict(unsigned) | {"signature": _b64(CryptoProvider.sign(self.private, unsigned.signing_bytes()))}))
        self.server.upload(envelope); return envelope
    def consume(self, envelope: SyncEnvelope) -> bytes:
        aad = canonical_bytes({"project": envelope.project_id, "object": envelope.object_id, "sequence": envelope.sequence})
        return CryptoProvider.decrypt(self.project_key, _unb64(envelope.nonce), _unb64(envelope.ciphertext), aad)


class OfflineQueue:
    """Durable, bounded retry queue for a transport implementing ``upload``."""
    def __init__(self, path: Path | str, *, max_items: int = 1000):
        self.path, self.max_items = Path(path), max_items; self.db = sqlite3.connect(str(self.path))
        self.db.execute("CREATE TABLE IF NOT EXISTS queue (id TEXT PRIMARY KEY, envelope TEXT NOT NULL, attempts INTEGER NOT NULL, next_at REAL NOT NULL)"); self.db.commit()
    def close(self): self.db.close()
    def enqueue(self, envelope: SyncEnvelope) -> None:
        if self.db.execute("SELECT COUNT(*) FROM queue").fetchone()[0] >= self.max_items: raise PlatformError("offline queue is full")
        queue_id = ":".join((envelope.project_id, envelope.sender_device, envelope.object_id, str(envelope.sequence)))
        self.db.execute("INSERT OR IGNORE INTO queue VALUES(?,?,?,?)", (queue_id, json.dumps(asdict(envelope), sort_keys=True), 0, 0.0)); self.db.commit()
    def flush(self, transport: Any, *, now: float | None = None, limit: int = 100) -> tuple[int, int]:
        sent = failed = 0; point = time.time() if now is None else now
        rows = self.db.execute("SELECT id,envelope,attempts FROM queue WHERE next_at<=? ORDER BY id LIMIT ?", (point, limit)).fetchall()
        for item_id, raw, attempts in rows:
            try:
                transport.upload(SyncEnvelope(**json.loads(raw))); self.db.execute("DELETE FROM queue WHERE id=?", (item_id,)); sent += 1
            except Exception:
                attempts += 1; self.db.execute("UPDATE queue SET attempts=?,next_at=? WHERE id=?", (attempts, point + min(300, 2 ** min(attempts, 8)), item_id)); failed += 1
        self.db.commit(); return sent, failed


ROLE_PERMISSIONS = {"owner": {"read", "write", "invite", "admin"}, "editor": {"read", "write"}, "viewer": {"read"}}


class TeamService:
    def __init__(self): self.orgs: dict[str, dict[str, Any]] = {}; self.invitations: dict[str, dict[str, Any]] = {}; self.audit: list[dict[str, Any]] = []
    def create_workspace(self, org: str, workspace: str, owner: Principal) -> None:
        if owner.organization_id != org or owner.workspace_id != workspace: raise AuthorizationDenied("tenant binding failed")
        self.orgs.setdefault(org, {"workspaces": {}})["workspaces"][workspace] = {owner.user_id: "owner"}
        self.audit.append({"op": "workspace.create", "org": org, "workspace": workspace, "actor": owner.user_id})
    def invite(self, actor: Principal, target_user: str, role: str) -> str:
        members = self.orgs.get(actor.organization_id, {}).get("workspaces", {}).get(actor.workspace_id)
        if not members or members.get(actor.user_id) not in {"owner"}: raise AuthorizationDenied("invite requires owner")
        if role not in ROLE_PERMISSIONS: raise PlatformError("unknown role")
        token = secrets.token_urlsafe(24); self.invitations[canonical_hash(token)] = {"org": actor.organization_id, "workspace": actor.workspace_id, "target": target_user, "role": role}
        self.audit.append({"op": "invite.issue", "token_digest": canonical_hash(token), "target": target_user, "role": role}); return token
    def accept(self, invitation: str, actor: Principal) -> None:
        if not invitation: raise PlatformError("malformed invitation")
        invite = self.invitations.pop(canonical_hash(invitation), None)
        if not invite or invite["org"] != actor.organization_id or invite["workspace"] != actor.workspace_id or invite["target"] != actor.user_id:
            raise AuthorizationDenied("invalid, expired, or misbound invitation")
        members = self.orgs.get(actor.organization_id, {}).get("workspaces", {}).get(actor.workspace_id)
        if members is None: raise AuthorizationDenied("unknown tenant")
        members[actor.user_id] = invite["role"]; self.audit.append({"op": "invite.accept", "actor": actor.user_id, "role": invite["role"]})
    def authorize(self, actor: Principal, operation: str) -> None:
        members = self.orgs.get(actor.organization_id, {}).get("workspaces", {}).get(actor.workspace_id, {})
        if operation not in ROLE_PERMISSIONS.get(members.get(actor.user_id), set()): raise AuthorizationDenied("team operation denied")
    def revoke(self, actor: Principal, user_id: str) -> None:
        self.authorize(actor, "admin"); members = self.orgs[actor.organization_id]["workspaces"][actor.workspace_id]; members.pop(user_id, None)
        self.audit.append({"op": "member.revoke", "actor": actor.user_id, "target": user_id})


PLANS = {"free": {"devices": 1, "seats": 1, "sync_objects": 100}, "pro": {"devices": 5, "seats": 1, "sync_objects": 10_000}, "team": {"devices": 100, "seats": 25, "sync_objects": 100_000}}


class EntitlementService:
    def __init__(self): self.subscriptions: dict[str, dict[str, Any]] = {}; self.usage: dict[tuple[str, str], int] = {}; self.events: set[str] = set(); self.audit: list[dict[str, Any]] = []
    def subscribe(self, org: str, plan: str, *, expires_at: str | None = None) -> None:
        if plan not in PLANS: raise PlatformError("unknown plan")
        self.subscriptions[org] = {"plan": plan, "state": "active", "expires_at": expires_at}
        self.audit.append({"event": "subscription.active", "organization": org, "plan": plan})
    def change(self, org: str, plan: str) -> None: self.subscribe(org, plan, expires_at=self.subscriptions.get(org, {}).get("expires_at"))
    def revoke(self, org: str) -> None:
        if org in self.subscriptions: self.subscriptions[org]["state"] = "revoked"
        self.audit.append({"event": "subscription.revoked", "organization": org})
    def apply_billing_event(self, event_id: str, org: str, event: str, **payload: Any) -> bool:
        if not event_id or event_id in self.events: return False
        if event == "subscription.updated": self.subscribe(org, str(payload["plan"]), expires_at=payload.get("expires_at"))
        elif event in {"subscription.revoked", "subscription.suspended"}: self.revoke(org)
        else: raise PlatformError("unknown billing event")
        self.events.add(event_id); self.audit.append({"event": event, "event_id": event_id, "organization": org}); return True
    def permit(self, org: str, feature: str, amount: int = 1) -> bool:
        sub = self.subscriptions.get(org); plan = PLANS.get(sub.get("plan")) if sub and sub.get("state") == "active" and (not sub.get("expires_at") or sub["expires_at"] >= utc_now()) else None
        if not plan: return False
        limit = plan.get(feature, 0); used = self.usage.get((org, feature), 0)
        if used + amount > limit: return False
        self.usage[(org, feature)] = used + amount; return True
    def status(self, org: str) -> dict[str, Any]:
        sub = self.subscriptions.get(org, {"plan": "free", "state": "inactive"})
        return redact_obj({"subscription": sub, "usage": {k[1]: v for k, v in self.usage.items() if k[0] == org}})


def integrated_local_flow(root: Path | str) -> dict[str, Any]:
    """Exercise identity, signing, encrypted sync, team auth, revocation, and billing."""
    root = Path(root); root.mkdir(parents=True, exist_ok=True); registry = TrustRegistry()
    first, first_private = create_device("org", "ws", "project", "alice", registry=registry)
    second, second_private = create_device("org", "ws", "project", "bob", registry=registry)
    server = LocalSyncServer(root / "sync.db", registry=registry); key = secrets.token_bytes(32)
    one = SyncClient(first, first_private, key, server); two = SyncClient(second, second_private, key, server)
    envelope = one.publish("object-1", b"workspace change", sequence=1)
    assert two.consume(server.pull(second, "project")[0]) == b"workspace change"
    two.publish("object-1", b"workspace change v2", sequence=1, base_digest=envelope.digest())
    conflict_detected = False
    try: one.publish("object-1", b"stale change", sequence=2, base_digest=envelope.digest())
    except ConflictError: conflict_detected = True
    team = TeamService(); team.create_workspace("org", "ws", first.principal)
    invitation = team.invite(first.principal, "bob", "editor"); team.accept(invitation, second.principal)
    team.authorize(second.principal, "write"); team.revoke(first.principal, "bob")
    try: team.authorize(second.principal, "write"); raise AssertionError("revoked member was authorized")
    except AuthorizationDenied: pass
    billing = EntitlementService(); billing.subscribe("org", "free"); allowed = billing.permit("org", "sync_objects")
    # Exercise a real disposable Git fixture and the worktree approval path.
    from .authorization import Grant
    from .worktree import State, SyntheticGitAdapter, WorktreeManager
    fixture = root / "git-fixture"; fixture.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=fixture, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "platform@example.com"], cwd=fixture, check=True)
    subprocess.run(["git", "config", "user.name", "Platform"], cwd=fixture, check=True)
    (fixture / "README.md").write_text("fixture\n"); subprocess.run(["git", "add", "."], cwd=fixture, check=True); subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=fixture, check=True)
    worktrees = WorktreeManager(root / "worktree-state", adapter=SyntheticGitAdapter(fixture), protected_roots=[fixture])
    create_grant = Grant(first.principal, "worktree.create", "repository")
    record = worktrees.create(fixture, task_id="platform-flow", owner=first.principal, grants=[create_grant])
    (Path(record.path) / "change.txt").write_text("change\n"); subprocess.run(["git", "add", "."], cwd=record.path, check=True); subprocess.run(["git", "commit", "-q", "-m", "change"], cwd=record.path, check=True)
    worktrees.transition(record.worktree_id, State.READY_FOR_REVIEW); worktrees.preview_merge(record.worktree_id)
    merge_grant = Grant(first.principal, "worktree.merge", record.worktree_id); worktrees.merge(worktrees.approve(record.worktree_id, operation="merge", actor=first.principal, grants=[merge_grant], target_ref="main"))
    (worktrees.worktrees_root / "interrupted-unknown").mkdir(); recovery = worktrees.recover()
    server.close(); return {"devices": 2, "encrypted_sync": True, "team_revocation": True, "entitlement_enforced": allowed, "conflict_detected": conflict_detected, "worktree_merged": True, "recovery_blocked_unknown": any(item.state.value == "BLOCKED" for item in recovery), "audit_events": len(team.audit) + len(billing.audit), "ciphertext": envelope.ciphertext}
