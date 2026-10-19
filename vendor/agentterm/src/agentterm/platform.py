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
import threading
import contextlib
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class SequenceConflict(PlatformError):
    pass


class StaleEnvelope(PlatformError):
    pass


class SyncTransportError(PlatformError):
    """Classified failure returned by a sync transport."""
    def __init__(self, message: str, *, status: int, code: str):
        super().__init__(message)
        self.status, self.code = status, code


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
    """Native Security.framework adapter; activation remains review-gated."""
    production_ready = False
    def __init__(self, service: str = "com.agentterm.identity", account: str = "default", *, helper=None, runner=None):
        if runner is not None: self._runner = runner; self._storage = None; return
        if helper is None: raise PlatformError("native Keychain helper path is required; refusing insecure fallback")
        from .keychain import NativeKeychainStorage
        self._storage = NativeKeychainStorage(helper, service=service); self._runner = None; self.account = account
    def put(self, key_id: str, private: bytes) -> None:
        if self._runner is not None: return self._runner("put", key_id, private)
        self._storage.put(key_id, private)
    def get(self, key_id: str) -> bytes:
        if self._runner is not None: return self._runner("get", key_id)
        return self._storage.get(key_id)
    def delete(self, key_id: str) -> None:
        if self._runner is not None: return self._runner("delete", key_id)
        self._storage.delete(key_id)


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
    replay_window = 256
    def __init__(self, path: Path | str, *, registry: TrustRegistry, rate_limit: int = 100, replay_window: int | None = None):
        self.path = Path(path); self.registry = registry; self.rate_limit = rate_limit; self.replay_window = replay_window or self.replay_window; self._upload_times: list[float] = []; self._rate_lock = threading.Lock(); self._closed = False; self._initialize_schema()
    def _connect(self) -> sqlite3.Connection:
        if self._closed: raise PlatformError("sync server is closed")
        connection = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=30000"); connection.execute("PRAGMA journal_mode=WAL"); return connection
    @contextlib.contextmanager
    def connection(self):
        """Yield a short-lived connection owned exclusively by this caller."""
        connection = self._connect()
        try: yield connection
        finally: connection.close()
    def _initialize_schema(self) -> None:
        with self.connection() as db:
            self._initialize_schema_on(db)
    def _initialize_schema_on(self, db: sqlite3.Connection) -> None:
        db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        columns = {row[1] for row in db.execute("PRAGMA table_info(objects)")}
        if columns and "sender_device" not in columns:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("CREATE TABLE objects_v2 (project TEXT, object_id TEXT, sender_device TEXT, sequence INTEGER, envelope TEXT, digest TEXT, PRIMARY KEY(project, object_id, sender_device, sequence))")
                for project, object_id, sequence, raw, digest in db.execute("SELECT project,object_id,sequence,envelope,digest FROM objects"):
                    sender = json.loads(raw)["sender_device"]; db.execute("INSERT INTO objects_v2 VALUES(?,?,?,?,?,?)", (project, object_id, sender, sequence, raw, digest))
                db.execute("ALTER TABLE objects RENAME TO objects_legacy"); db.execute("ALTER TABLE objects_v2 RENAME TO objects"); db.execute("DROP TABLE objects_legacy"); db.execute("INSERT OR REPLACE INTO meta VALUES('schema_version','2')"); db.commit()
            except Exception:
                db.rollback(); raise
        else:
            db.execute("CREATE TABLE IF NOT EXISTS objects (project TEXT, object_id TEXT, sender_device TEXT, sequence INTEGER, envelope TEXT, digest TEXT, PRIMARY KEY(project, object_id, sender_device, sequence))")
            db.execute("INSERT OR REPLACE INTO meta VALUES('schema_version','2')")
        db.execute("CREATE TABLE IF NOT EXISTS sequences (device TEXT, project TEXT, sequence INTEGER, digest TEXT, PRIMARY KEY(device, project, sequence))")
        db.execute("CREATE TABLE IF NOT EXISTS cursors (device TEXT, project TEXT, sequence INTEGER, PRIMARY KEY(device, project))"); db.commit()
    def close(self): self._closed = True
    def health(self) -> dict[str, Any]:
        with self.connection() as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            objects = db.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
            return {"ok": integrity == "ok", "integrity": integrity, "schema_version": version[0] if version else None, "objects": objects, "protocol": self.protocol_version}
    def backup(self, destination: Path | str) -> Path:
        """Create an atomic SQLite backup; the source remains untouched."""
        target = Path(destination); target.parent.mkdir(parents=True, exist_ok=True); temporary = target.with_suffix(target.suffix + ".tmp")
        with self.connection() as source:
            backup = sqlite3.connect(str(temporary), timeout=30, isolation_level=None)
            try: source.backup(backup); backup.commit()
            finally: backup.close()
        os.replace(temporary, target); return target
    @staticmethod
    def quarantine_corrupt(path: Path | str) -> Path:
        """Move a corrupt local database aside without deleting it."""
        source = Path(path)
        if not source.exists(): raise PlatformError("sync database does not exist")
        target = source.with_name(source.name + ".corrupt-" + uuid.uuid4().hex)
        os.replace(source, target)
        return target
    def negotiate(self, version: str) -> bool:
        return version == self.protocol_version
    def upload(self, envelope: SyncEnvelope) -> None:
        now = time.monotonic()
        with self._rate_lock:
            self._upload_times = [point for point in self._upload_times if now - point < 60]
            if len(self._upload_times) >= self.rate_limit: raise PlatformError("sync rate limit exceeded")
            self._upload_times.append(now)
        if envelope.schema != self.protocol_version or envelope.sequence < 0: raise PlatformError("invalid sync envelope")
        if len(canonical_bytes(asdict(envelope))) > self.max_envelope_bytes: raise PlatformError("sync envelope exceeds size limit")
        device = self.registry.get(envelope.key_id)
        if device.owner.device_id != envelope.sender_device or device.owner.project_id != envelope.project_id: raise PlatformError("sender/project binding failed")
        if not CryptoProvider.verify(_unb64(device.public_key), envelope.signing_bytes(), _unb64(envelope.signature)): raise PlatformError("invalid sync signature")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute("SELECT digest FROM objects WHERE project=? AND object_id=? AND sender_device=? AND sequence=?", (envelope.project_id, envelope.object_id, envelope.sender_device, envelope.sequence)).fetchone()
                if existing:
                    if existing[0] == envelope.digest(): db.commit(); return
                    raise SequenceConflict("sequence already contains a different envelope")
                seen = db.execute("SELECT digest FROM sequences WHERE device=? AND project=? AND sequence=?", (envelope.sender_device, envelope.project_id, envelope.sequence)).fetchone()
                if seen: raise SequenceConflict("sequence already contains a different envelope")
                latest = db.execute("SELECT envelope, digest FROM objects WHERE project=? AND object_id=? ORDER BY rowid DESC LIMIT 1", (envelope.project_id, envelope.object_id)).fetchone()
                if latest and envelope.base_digest != latest[1]: raise ConflictError("object has diverged; resolve against the latest envelope")
                raw = json.dumps(asdict(envelope), sort_keys=True)
                prior = db.execute("SELECT MAX(sequence) FROM sequences WHERE device=? AND project=?", (envelope.sender_device, envelope.project_id)).fetchone()[0]
                if prior is not None and envelope.sequence <= prior - self.replay_window: raise StaleEnvelope("sequence is outside the replay window")
                db.execute("INSERT INTO sequences VALUES(?,?,?,?)", (envelope.sender_device, envelope.project_id, envelope.sequence, envelope.digest()))
                db.execute("INSERT INTO objects VALUES(?,?,?,?,?,?)", (envelope.project_id, envelope.object_id, envelope.sender_device, envelope.sequence, raw, envelope.digest())); db.commit()
            except Exception:
                db.rollback(); raise
    def pull(self, device: Device, project: str, after: int = 0) -> list[SyncEnvelope]:
        if device.status != "active": raise AuthorizationDenied("device is revoked")
        try:
            trusted = self.registry.get(device.key_id, device.principal)
        except PlatformError as exc:
            raise AuthorizationDenied("device is not trusted") from exc
        if trusted.owner.device_id != device.device_id or trusted.public_key != device.public_key:
            raise AuthorizationDenied("device identity binding failed")
        if device.principal.project_id != project: raise AuthorizationDenied("cross-project sync denied")
        with self.connection() as db: rows = db.execute("SELECT envelope FROM objects WHERE project=? AND sequence>? ORDER BY sequence", (project, after)).fetchall()
        return [SyncEnvelope(**json.loads(row[0])) for row in rows]
    def advance_cursor(self, device: Device, project: str, sequence: int) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                old = db.execute("SELECT sequence FROM cursors WHERE device=? AND project=?", (device.device_id, project)).fetchone()
                if old and sequence < old[0]: raise PlatformError("cursor rollback")
                db.execute("INSERT OR REPLACE INTO cursors VALUES(?,?,?)", (device.device_id, project, sequence)); db.commit()
            except Exception:
                db.rollback(); raise


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
        self.path, self.max_items, self._closed = Path(path), max_items, False
        with self.connection() as db: db.execute("CREATE TABLE IF NOT EXISTS queue (id TEXT PRIMARY KEY, envelope TEXT NOT NULL, attempts INTEGER NOT NULL, next_at REAL NOT NULL)"); db.commit()
    def _connect(self) -> sqlite3.Connection:
        if self._closed: raise PlatformError("offline queue is closed")
        connection = sqlite3.connect(str(self.path), timeout=30, isolation_level=None); connection.execute("PRAGMA busy_timeout=30000"); connection.execute("PRAGMA journal_mode=WAL"); return connection
    @contextlib.contextmanager
    def connection(self):
        db = self._connect()
        try: yield db
        finally: db.close()
    def close(self): self._closed = True
    def enqueue(self, envelope: SyncEnvelope) -> None:
        with self.connection() as db:
            if db.execute("SELECT COUNT(*) FROM queue").fetchone()[0] >= self.max_items: raise PlatformError("offline queue is full")
            queue_id = ":".join((envelope.project_id, envelope.sender_device, envelope.object_id, str(envelope.sequence)))
            db.execute("INSERT OR IGNORE INTO queue VALUES(?,?,?,?)", (queue_id, json.dumps(asdict(envelope), sort_keys=True), 0, 0.0)); db.commit()
    def flush(self, transport: Any, *, now: float | None = None, limit: int = 100) -> tuple[int, int]:
        sent = failed = 0; point = time.time() if now is None else now
        with self.connection() as db:
            rows = db.execute("SELECT id,envelope,attempts FROM queue WHERE next_at<=? ORDER BY id LIMIT ?", (point, limit)).fetchall()
            for item_id, raw, attempts in rows:
                try:
                    transport.upload(SyncEnvelope(**json.loads(raw))); db.execute("DELETE FROM queue WHERE id=?", (item_id,)); sent += 1
                except Exception:
                    attempts += 1; db.execute("UPDATE queue SET attempts=?,next_at=? WHERE id=?", (attempts, point + min(300, 2 ** min(attempts, 8)), item_id)); failed += 1
            db.commit(); return sent, failed


class LoopbackSyncService:
    """Development HTTP transport; loopback-only and explicitly not production TLS."""
    def __init__(self, server: LocalSyncServer, *, token: str | None = None, max_body: int = 1 << 20):
        self.server, self.token, self.max_body = server, token or secrets.token_urlsafe(32), max_body
        self._lifecycle_lock = threading.Lock()
        service = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args): pass
            def _auth(self) -> bool:
                return self.headers.get("Authorization") == "Bearer " + service.token
            def _reply(self, code: int, body: dict[str, Any]):
                raw = json.dumps(body, sort_keys=True).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_POST(self):
                if not self._auth(): return self._reply(401, {"error": "unauthorized"})
                if self.path != "/v1/upload": return self._reply(404, {"error": "not found"})
                length = int(self.headers.get("Content-Length", "-1"))
                if length < 0 or length > service.max_body: return self._reply(413, {"error": "payload too large"})
                try:
                    envelope = SyncEnvelope(**json.loads(self.rfile.read(length))); service.server.upload(envelope); self._reply(200, {"ok": True})
                except ConflictError as exc: self._reply(409, {"error": str(exc)[:200], "code": "conflict"})
                except SequenceConflict as exc: self._reply(409, {"error": str(exc)[:200], "code": "sequence_conflict"})
                except StaleEnvelope as exc: self._reply(409, {"error": str(exc)[:200], "code": "stale_envelope"})
                except AuthorizationDenied as exc: self._reply(403, {"error": str(exc)[:200], "code": "authorization_denied"})
                except Exception as exc: self._reply(400, {"error": str(exc)[:200], "code": "invalid_request"})
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/healthz": return self._reply(200, {"ok": service.server.health()["ok"], "protocol": service.server.protocol_version})
                if parsed.path == "/readyz":
                    try: service.server.health(); return self._reply(200, {"ok": True})
                    except Exception: return self._reply(503, {"ok": False, "code": "not_ready"})
                if not self._auth(): return self._reply(401, {"error": "unauthorized"})
                if parsed.path != "/v1/pull": return self._reply(404, {"error": "not found"})
                try:
                    query = urllib.parse.parse_qs(parsed.query); project = query.get("project", [""])[0]; after = int(query.get("after", ["0"])[0])
                    envelopes = service.server.pull_for_device(query.get("device", [""])[0], project, after); self._reply(200, {"envelopes": [asdict(item) for item in envelopes]})
                except AuthorizationDenied as exc: self._reply(403, {"error": str(exc)[:200], "code": "authorization_denied"})
                except Exception as exc: self._reply(400, {"error": str(exc)[:200], "code": "invalid_request"})
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler); self.thread: threading.Thread | None = None
    @property
    def address(self) -> tuple[str, int]: return self.http.server_address
    def start(self) -> None:
        with self._lifecycle_lock:
            if self.thread and self.thread.is_alive(): return
            self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
    def close(self) -> None:
        with self._lifecycle_lock:
            thread = self.thread
            if not thread: self.http.server_close(); return
            self.http.shutdown(); self.http.server_close(); thread.join(timeout=2); self.thread = None


def _server_pull_for_device(server: LocalSyncServer, device_id: str, project: str, after: int) -> list[SyncEnvelope]:
    for key in server.registry._keys.values():
        if key.owner.device_id == device_id:
            device = Device(device_id, key.owner, key.key_id, key.public_key); return server.pull(device, project, after)
    raise AuthorizationDenied("unknown device")


LocalSyncServer.pull_for_device = _server_pull_for_device  # type: ignore[attr-defined]


class LoopbackSyncTransport:
    def __init__(self, service: LoopbackSyncService): self.service, self.token = service, service.token
    def _request(self, method: str, path: str, payload: bytes | None = None) -> dict[str, Any]:
        host, port = self.service.address; request = urllib.request.Request(f"http://{host}:{port}{path}", data=payload, method=method, headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response: return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                try: body = json.loads(exc.read().decode(errors="replace"))
                except json.JSONDecodeError: body = {"error": "sync transport rejected request", "code": "http_error"}
            finally:
                exc.close()
            raise SyncTransportError(str(body.get("error", "sync transport rejected request")), status=exc.code, code=str(body.get("code", "http_error"))) from exc
    def upload(self, envelope: SyncEnvelope) -> None: self._request("POST", "/v1/upload", canonical_bytes(asdict(envelope)))
    def pull(self, device: Device, project: str, after: int = 0) -> list[SyncEnvelope]:
        query = urllib.parse.urlencode({"device": device.device_id, "project": project, "after": after}); return [SyncEnvelope(**item) for item in self._request("GET", "/v1/pull?" + query)["envelopes"]]


ROLE_PERMISSIONS = {"owner": {"read", "write", "invite", "admin"}, "editor": {"read", "write"}, "viewer": {"read"}}


class TeamService:
    def __init__(self, entitlements: "EntitlementService | None" = None): self.orgs: dict[str, dict[str, Any]] = {}; self.invitations: dict[str, dict[str, Any]] = {}; self.audit: list[dict[str, Any]] = []; self.entitlements = entitlements
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
        if actor.user_id in members: raise AuthorizationDenied("user is already a workspace member")
        if self.entitlements and not self.entitlements.permit(actor.organization_id, "seats"):
            raise AuthorizationDenied("seat entitlement exhausted")
        members[actor.user_id] = invite["role"]; self.audit.append({"op": "invite.accept", "actor": actor.user_id, "role": invite["role"]})
    def authorize(self, actor: Principal, operation: str) -> None:
        members = self.orgs.get(actor.organization_id, {}).get("workspaces", {}).get(actor.workspace_id, {})
        if operation not in ROLE_PERMISSIONS.get(members.get(actor.user_id), set()): raise AuthorizationDenied("team operation denied")
    def revoke(self, actor: Principal, user_id: str) -> None:
        self.authorize(actor, "admin"); members = self.orgs[actor.organization_id]["workspaces"][actor.workspace_id]
        removed = members.pop(user_id, None)
        if removed is not None and self.entitlements: self.entitlements.release(actor.organization_id, "seats")
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
        if amount <= 0: raise PlatformError("entitlement amount must be positive")
        sub = self.subscriptions.get(org); plan = PLANS.get(sub.get("plan")) if sub and sub.get("state") == "active" and (not sub.get("expires_at") or sub["expires_at"] >= utc_now()) else None
        if not plan: return False
        limit = plan.get(feature, 0); used = self.usage.get((org, feature), 0)
        if used + amount > limit: return False
        self.usage[(org, feature)] = used + amount; return True
    def release(self, org: str, feature: str, amount: int = 1) -> None:
        if amount <= 0: raise PlatformError("entitlement amount must be positive")
        key = (org, feature); self.usage[key] = max(0, self.usage.get(key, 0) - amount)
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
    health_before = server.health(); backup = server.backup(root / "sync-backup.db")
    queue = OfflineQueue(root / "offline.db"); queue.enqueue(envelope); queued_result = queue.flush(server, now=1); queue.close()
    server.close(); restarted = LocalSyncServer(root / "sync.db", registry=registry); restarted.upload(envelope); health_after = restarted.health(); restarted.close()
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
    return {"devices": 2, "encrypted_sync": True, "team_revocation": True, "entitlement_enforced": allowed, "conflict_detected": conflict_detected, "worktree_merged": True, "recovery_blocked_unknown": any(item.state.value == "BLOCKED" for item in recovery), "audit_events": len(team.audit) + len(billing.audit), "backup_created": backup.exists(), "queue_recovered": queued_result == (1, 0), "restart_replay_idempotent": health_before["ok"] and health_after["ok"], "ciphertext": envelope.ciphertext}


def integrated_staging_flow(root: Path | str) -> dict[str, Any]:
    """Exercise the actual local HTTP service with synthetic external providers."""
    from .integration import BillingWebhookVerifier, OIDCValidator
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    registry = TrustRegistry(); alice, private = create_device("org", "workspace", "project", "alice", registry=registry); bob, _ = create_device("org", "workspace", "project", "bob", registry=registry)
    server = LocalSyncServer(root / "sync.db", registry=registry); service = LoopbackSyncService(server); service.start(); restarted = None
    try:
        transport = LoopbackSyncTransport(service); client = SyncClient(alice, private, b"s" * 32, transport)
        first = client.publish("staging", b"staging", sequence=1)
        for sequence in range(2, 6): client.publish("staging-" + str(sequence), b"concurrent", sequence=sequence)
        pulled = transport.pull(bob, "project")
        claims = {"iss": "https://synthetic.example", "aud": "agentterm", "sub": "alice", "exp": time.time() + 60, "organization_id": "org", "workspace_id": "workspace", "project_id": "project"}
        principal = OIDCValidator(issuer="https://synthetic.example", audience="agentterm").validate(claims)
        billing_private, billing_public = CryptoProvider.signing_key(); event = {"id": "staging-event", "issued_at": time.time(), "organization": "org", "event": "subscription.updated"}
        verifier = BillingWebhookVerifier(billing_public); verified_event = verifier.verify(event, CryptoProvider.sign(billing_private, canonical_bytes(event)))
        health = urllib.request.urlopen("http://%s:%s/healthz" % service.address, timeout=5).read()
        backup = server.backup(root / "staging-backup.db"); service.close(); server.close(); restarted = LocalSyncServer(backup, registry=registry)
        restart_health = restarted.health()
        return {"http_health": json.loads(health)["ok"], "objects": len(pulled), "signed_sync": first.project_id == principal.project_id, "oidc_tenant": principal.organization_id == "org", "billing_webhook": verified_event["id"] == "staging-event", "backup_restored": backup.exists() and restart_health["ok"], "server_restart_safe": restart_health["objects"] == 5}
    finally:
        service.close(); server.close()
        if restarted: restarted.close()
