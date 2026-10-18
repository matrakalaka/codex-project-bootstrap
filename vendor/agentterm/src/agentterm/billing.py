"""Deterministic mock billing provider and ordered entitlement adapter."""
from __future__ import annotations

import time
from typing import Any, Callable

from .canon import canonical_bytes
from .integration import BillingWebhookVerifier, IntegrationError
from .platform import CryptoProvider, EntitlementService


class MockBillingProvider:
    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock; self.private, self.public = CryptoProvider.signing_key(); self.events = {}

    def event(self, event_id: str, organization: str, name: str, *, sequence: int, plan: str | None = None, issued_at: float | None = None, **extra: Any) -> tuple[dict[str, Any], bytes]:
        payload = {"id": event_id, "organization": organization, "event": name, "sequence": sequence, "issued_at": self.clock() if issued_at is None else issued_at} | extra
        if plan is not None: payload["plan"] = plan
        return payload, CryptoProvider.sign(self.private, canonical_bytes(payload))

    def deliver(self, service: "BillingAdapter", event: dict[str, Any], signature: bytes) -> bool:
        return service.apply(event, signature, self.public)


class BillingAdapter:
    def __init__(self, entitlements: EntitlementService, public_key: bytes, *, clock: Callable[[], float] = time.time):
        self.entitlements, self.verifier, self.clock, self.sequences, self.audit = entitlements, BillingWebhookVerifier(public_key, clock=clock), clock, {}, []

    def apply(self, event: dict[str, Any], signature: bytes, public_key: bytes) -> bool:
        if public_key != self.verifier.public_key: raise IntegrationError("billing provider key mismatch")
        verified = self.verifier.verify(event, signature); org, sequence = verified.get("organization"), verified.get("sequence")
        if not isinstance(org, str) or not isinstance(sequence, int): raise IntegrationError("billing event binding missing")
        if sequence <= self.sequences.get(org, 0): return False
        name = verified.get("event")
        if name in {"subscription.updated", "subscription.trial"}: self.entitlements.subscribe(org, str(verified["plan"]), expires_at=verified.get("expires_at"))
        elif name in {"subscription.canceled", "payment.failed", "subscription.revoked"}: self.entitlements.revoke(org)
        elif name == "payment.succeeded": pass
        else: raise IntegrationError("unknown billing event")
        self.sequences[org] = sequence; self.audit.append({"event": name, "organization": org, "sequence": sequence}); return True
