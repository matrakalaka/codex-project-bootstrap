"""Optional PostgreSQL sync store for distributed deployment.

The adapter accepts an injected DB-API connection factory, so importing
AgentTerm never installs or silently selects a database driver. PostgreSQL
constraints, transactions, and row locks own replay/cursor consistency.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Callable

from .platform import AuthorizationDenied, ConflictError, CryptoProvider, LocalSyncServer, PlatformError, SequenceConflict, StaleEnvelope, SyncEnvelope, TrustRegistry, _b64, _unb64


class PostgresUnavailable(PlatformError):
    pass


class PostgresSyncStore:
    def __init__(self, connect: Callable[[], Any], *, registry: TrustRegistry, replay_window: int = 256):
        self.connect, self.registry, self.replay_window = connect, registry, replay_window

    @contextmanager
    def transaction(self):
        try: connection = self.connect()
        except Exception as exc: raise PostgresUnavailable("PostgreSQL connection unavailable") from exc
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally: connection.close()

    def initialize(self) -> None:
        with self.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TABLE IF NOT EXISTS agentterm_objects (project TEXT NOT NULL, object_id TEXT NOT NULL, sender_device TEXT NOT NULL, sequence BIGINT NOT NULL, envelope TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(project, object_id, sender_device, sequence))")
                cursor.execute("CREATE TABLE IF NOT EXISTS agentterm_sequences (device TEXT NOT NULL, project TEXT NOT NULL, sequence BIGINT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(device, project, sequence))")
                cursor.execute("CREATE TABLE IF NOT EXISTS agentterm_cursors (device TEXT NOT NULL, project TEXT NOT NULL, sequence BIGINT NOT NULL, PRIMARY KEY(device, project))")

    def _verify(self, envelope: SyncEnvelope) -> None:
        if envelope.schema != LocalSyncServer.protocol_version or envelope.sequence < 0: raise PlatformError("invalid sync envelope")
        key = self.registry.get(envelope.key_id)
        if key.owner.device_id != envelope.sender_device or key.owner.project_id != envelope.project_id: raise AuthorizationDenied("sender/project binding failed")
        if not CryptoProvider.verify(_unb64(key.public_key), envelope.signing_bytes(), _unb64(envelope.signature)): raise PlatformError("invalid sync signature")

    def upload(self, envelope: SyncEnvelope) -> None:
        self._verify(envelope); raw, digest = json.dumps(asdict(envelope), sort_keys=True), envelope.digest()
        with self.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT digest FROM agentterm_objects WHERE project=%s AND object_id=%s AND sender_device=%s AND sequence=%s FOR UPDATE", (envelope.project_id, envelope.object_id, envelope.sender_device, envelope.sequence)); existing = cursor.fetchone()
                if existing:
                    if existing[0] == digest: return
                    raise SequenceConflict("sequence already contains a different envelope")
                cursor.execute("SELECT digest FROM agentterm_sequences WHERE device=%s AND project=%s AND sequence=%s FOR UPDATE", (envelope.sender_device, envelope.project_id, envelope.sequence))
                if cursor.fetchone(): raise SequenceConflict("sequence already contains a different envelope")
                cursor.execute(
                    "SELECT sequence FROM agentterm_sequences "
                    "WHERE device=%s AND project=%s "
                    "ORDER BY sequence DESC LIMIT 1 FOR UPDATE",
                    (envelope.sender_device, envelope.project_id),
                )
                prior_row = cursor.fetchone()
                prior = prior_row[0] if prior_row else None
                if prior is not None and envelope.sequence <= prior - self.replay_window: raise StaleEnvelope("sequence is outside the replay window")
                cursor.execute("SELECT digest FROM agentterm_objects WHERE project=%s AND object_id=%s ORDER BY sequence DESC LIMIT 1 FOR UPDATE", (envelope.project_id, envelope.object_id)); latest = cursor.fetchone()
                if latest and envelope.base_digest != latest[0]: raise ConflictError("object has diverged; resolve against the latest envelope")
                cursor.execute("INSERT INTO agentterm_sequences(device,project,sequence,digest) VALUES(%s,%s,%s,%s)", (envelope.sender_device, envelope.project_id, envelope.sequence, digest))
                cursor.execute("INSERT INTO agentterm_objects(project,object_id,sender_device,sequence,envelope,digest) VALUES(%s,%s,%s,%s,%s,%s)", (envelope.project_id, envelope.object_id, envelope.sender_device, envelope.sequence, raw, digest))

    def pull(self, device: Any, project: str, after: int = 0) -> list[SyncEnvelope]:
        if device.status != "active" or device.principal.project_id != project: raise AuthorizationDenied("sync read denied")
        self.registry.get(device.key_id, device.principal)
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT envelope FROM agentterm_objects WHERE project=%s AND sequence>%s ORDER BY sequence", (project, after)); rows = cursor.fetchall()
            return [SyncEnvelope(**(json.loads(row[0]) if isinstance(row[0], str) else row[0])) for row in rows]
        finally: connection.close()

    def pull_for_device(self, device_id: str, project: str, after: int = 0) -> list[SyncEnvelope]:
        for key in self.registry._keys.values():
            if key.owner.device_id == device_id:
                from .platform import Device
                return self.pull(Device(device_id, key.owner, key.key_id, key.public_key), project, after)
        raise AuthorizationDenied("unknown device")

    def health(self) -> dict[str, Any]:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM agentterm_objects"); objects = cursor.fetchone()[0]
            return {"ok": True, "integrity": "database connection verified", "objects": objects, "protocol": LocalSyncServer.protocol_version}
        finally: connection.close()

