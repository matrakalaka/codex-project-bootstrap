"""Non-operational contracts owned by Phase 0.

These records intentionally describe future boundaries without creating a
network client, billing integration, or Git mutation path.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .canon import canonical_hash

@dataclass(frozen=True)
class WorktreeLease:
    worktree_id: str; repository_identity: str; source_head: str; path: str
    branch: str; owner_device_id: str; task_id: str; state: str = "ALLOCATED"
    dirty_fingerprint: str | None = None
    def validate(self, repository_identity: str) -> None:
        if self.repository_identity != repository_identity: raise ValueError("worktree repository mismatch")
        if self.state not in {"ALLOCATED", "ACTIVE", "ORPHANED", "MERGED", "DISCARDED"}: raise ValueError("unknown worktree state")

@dataclass(frozen=True)
class SyncObject:
    object_id: str; project_id: str; sequence: int; content_digest: str
    envelope_digest: str; predecessor_digest: str | None = None; tombstone: bool = False
    def validate(self, project_id: str) -> None:
        if self.project_id != project_id: raise ValueError("sync object project mismatch")
        if self.sequence < 0: raise ValueError("sync sequence must be non-negative")

@dataclass(frozen=True)
class TeamMembership:
    organization_id: str; workspace_id: str; project_id: str; subject_id: str; role: str; status: str = "active"
    def can(self, operation: str) -> bool:
        if self.status != "active": return False
        return {"owner": {"read", "write", "approve", "admin"}, "editor": {"read", "write"}, "viewer": {"read"}}.get(self.role, set()).__contains__(operation)

@dataclass(frozen=True)
class Entitlement:
    account_id: str; product: str; state: str; source_event_id: str; valid_until: str | None = None
    def permits(self, feature: str) -> bool:
        return self.state == "active" and feature in {"sync", "team_memory", "audit_export"}

def contract_fingerprint(value: Any) -> str:
    return canonical_hash(value.__dict__ if hasattr(value, "__dict__") else value)
