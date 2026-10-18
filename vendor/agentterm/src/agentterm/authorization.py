"""Fail-closed authorization and provenance contracts for future services."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .canon import canonical_hash, utc_now
from .security import Principal

@dataclass(frozen=True)
class Grant:
    principal: Principal
    operation: str
    resource: str
    expires_at: str | None = None
    grant_id: str = ""

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    operation: str
    resource: str
    actor: Principal
    evaluated_at: str
    grant_id: str | None = None

def authorize(actor: Principal | None, operation: str, resource: str,
              grants: Iterable[Grant], *, now: str | None = None) -> Decision:
    timestamp = now or utc_now()
    if actor is None: return Decision(False, "missing actor", operation, resource, _anonymous(), timestamp)
    for grant in grants:
        if grant.principal != actor or grant.operation != operation or grant.resource != resource: continue
        if grant.expires_at and timestamp > grant.expires_at: continue
        return Decision(True, "explicit grant", operation, resource, actor, timestamp, grant.grant_id or None)
    return Decision(False, "no matching explicit grant", operation, resource, actor, timestamp)

def _anonymous() -> Principal:
    return Principal("anonymous", "anonymous", "anonymous", "anonymous")

@dataclass(frozen=True)
class AuditReceipt:
    receipt_id: str
    request_id: str
    actor: Principal
    operation: str
    resource: str
    decision: Decision
    result: str
    provenance: dict[str, str]
    previous_digest: str | None = None
    created_at: str = ""

    def as_dict(self) -> dict:
        return {"schema_version": "agentterm.audit-receipt.v0", "receipt_id": self.receipt_id,
                "request_id": self.request_id, "actor": self.actor.as_dict(), "operation": self.operation,
                "resource": self.resource, "decision": self.decision.allowed, "reason": self.decision.reason,
                "result": self.result, "provenance": self.provenance, "previous_digest": self.previous_digest,
                "created_at": self.created_at or self.decision.evaluated_at}

    def digest(self) -> str: return canonical_hash(self.as_dict())
