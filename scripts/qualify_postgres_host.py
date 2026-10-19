#!/usr/bin/env python3
"""Qualify AgentTerm's PostgreSQL-backed service with independent processes.

The script deliberately uses a caller-supplied disposable DSN. It never starts
or configures PostgreSQL, and it does not print tokens or envelope contents.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import psycopg

from agentterm.platform import LoopbackSyncService, SyncClient, TrustRegistry, create_device
from agentterm.postgres import PostgresSyncStore


def service_process(dsn: str, registry: TrustRegistry, command, ready) -> None:
    store = PostgresSyncStore(lambda: psycopg.connect(dsn), registry=registry)
    store.initialize()
    service = LoopbackSyncService(store)
    service.start()
    ready.send((service.address, service.token))
    try:
        command.recv()
    finally:
        service.close()


class ServiceProxy:
    def __init__(self, address, token):
        self.address, self.token = address, token


def request(proxy: ServiceProxy, method: str, path: str) -> dict:
    req = urllib.request.Request(
        f"http://{proxy.address[0]}:{proxy.address[1]}{path}",
        method=method,
        headers={"Authorization": "Bearer " + proxy.token},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    args = parser.parse_args()
    context = multiprocessing.get_context("fork")
    registry = TrustRegistry()
    alice, alice_private = create_device("org", "workspace", "project", "alice", registry=registry)
    bob, bob_private = create_device("org", "workspace", "project", "bob", registry=registry)
    parent_a, child_a = context.Pipe()
    parent_b, child_b = context.Pipe()
    ready_a, child_ready_a = context.Pipe()
    ready_b, child_ready_b = context.Pipe()
    processes = [
        context.Process(target=service_process, args=(args.dsn, registry, child_a, child_ready_a)),
        context.Process(target=service_process, args=(args.dsn, registry, child_b, child_ready_b)),
    ]
    for process in processes:
        process.start()
    proxies = [ServiceProxy(*ready.recv()) for ready in (ready_a, ready_b)]
    try:
        assert request(proxies[0], "GET", "/healthz")["ok"]
        assert request(proxies[1], "GET", "/readyz")["ok"]

        # Build signed envelopes without publishing, then submit through two
        # independent HTTP service processes concurrently.
        envelopes = []
        for number in range(1, 5):
            class Noop:
                def upload(self, envelope):
                    self.envelope = envelope
            noop = Noop()
            SyncClient(alice, alice_private, b"k" * 32, noop).publish(
                f"object-{number}", f"payload-{number}".encode(), sequence=number
            )
            envelopes.append(noop.envelope)

        def upload(index: int) -> None:
            proxy = proxies[index % 2]
            body = json.dumps(asdict(envelopes[index]), sort_keys=True).encode()
            req = urllib.request.Request(
                f"http://{proxy.address[0]}:{proxy.address[1]}/v1/upload",
                data=body,
                method="POST",
                headers={"Authorization": "Bearer " + proxy.token, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                assert response.status == 200

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(upload, range(len(envelopes))))

        query = urllib.parse.urlencode({"device": bob.device_id, "project": "project", "after": 0})
        assert len(request(proxies[0], "GET", "/v1/pull?" + query)["envelopes"]) == 4
        assert len(request(proxies[1], "GET", "/v1/pull?" + query)["envelopes"]) == 4
        store = PostgresSyncStore(lambda: psycopg.connect(args.dsn), registry=registry)
        store.advance_cursor(bob, "project", 4)
        assert store.cursor(bob, "project") == 4
        parent_b.send(True)
        processes[1].join(timeout=10)
        parent_b, child_b = context.Pipe()
        ready_b, child_ready_b = context.Pipe()
        processes[1] = context.Process(target=service_process, args=(args.dsn, registry, child_b, child_ready_b))
        processes[1].start()
        proxies[1] = ServiceProxy(*ready_b.recv())
        assert request(proxies[1], "GET", "/healthz")["ok"]
        assert len(request(proxies[1], "GET", "/v1/pull?" + query)["envelopes"]) == 4
        print(json.dumps({"health": True, "objects": 4, "multi_process": True, "restart": True}))
    finally:
        parent_a.send(True)
        parent_b.send(True)
        for process in processes:
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
