#!/usr/bin/env python3
"""Run the loopback AgentTerm service behind an approved HTTPS terminator.

The process owns no private signing keys. It loads public trust records and
receives the bearer secret only from the environment/secret manager boundary.
"""
from __future__ import annotations

import json
import os
import signal
import threading
from pathlib import Path

import psycopg

from agentterm.platform import LoopbackSyncService, PlatformError, TrustKey, TrustRegistry
from agentterm.postgres import PostgresSyncStore
from agentterm.security import Principal


def load_registry(path: str) -> TrustRegistry:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    registry = TrustRegistry()
    for item in body.get("keys", []):
        owner = Principal(**item["owner"])
        registry.add(TrustKey(
            key_id=item["key_id"], owner=owner, public_key=item["public_key"],
            status=item.get("status", "active"), predecessor=item.get("predecessor"),
            created_at=item.get("created_at", ""),
        ))
    return registry


def main() -> int:
    environment = os.environ.get("AGENTTERM_ENV", "")
    dsn = os.environ.get("AGENTTERM_DATABASE_URL", "")
    token = os.environ.get("AGENTTERM_SYNC_TOKEN", "")
    registry_path = os.environ.get("AGENTTERM_TRUST_REGISTRY", "")
    sync_url = os.environ.get("AGENTTERM_SYNC_URL", "")
    bind_host = os.environ.get("AGENTTERM_BIND_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("AGENTTERM_BIND_PORT", "8765"))
    except ValueError as exc:
        raise SystemExit("AGENTTERM_BIND_PORT must be an integer") from exc
    if environment not in {"staging", "production"}:
        raise SystemExit("AGENTTERM_ENV must be staging or production")
    if not dsn or not token or not registry_path:
        raise SystemExit("database URL, sync token, and trust registry are required")
    if environment == "production" and not sync_url.startswith("https://"):
        raise SystemExit("production sync URL must use HTTPS termination")
    if bind_host not in {"127.0.0.1", "::1"}:
        raise SystemExit("service must bind to loopback behind the TLS terminator")
    registry = load_registry(registry_path)
    store = PostgresSyncStore(lambda: psycopg.connect(dsn), registry=registry)
    store.initialize()
    service = LoopbackSyncService(store, token=token, bind_host=bind_host, bind_port=port)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    service.start()
    print(json.dumps({"ready": True, "host": service.address[0], "port": service.address[1]}), flush=True)
    try:
        stop.wait()
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
