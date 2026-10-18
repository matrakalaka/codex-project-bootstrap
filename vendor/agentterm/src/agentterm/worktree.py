"""Fail-closed, application-managed synthetic Git worktree isolation.

The production adapter is deliberately inert.  Only ``SyntheticGitAdapter``
may mutate a repository, and callers must explicitly identify a disposable
fixture.  Metadata is authenticated with a manager-local key, written
atomically, and protected by an inter-process lock.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Protocol

from .authorization import AuditReceipt, Grant, authorize
from .canon import canonical_bytes, canonical_hash, utc_now
from .gitinfo import Snapshot, snapshot
from .redact import redact_obj
from .security import Principal


class WorktreeError(RuntimeError):
    pass


class AuthorizationError(WorktreeError):
    pass


class IntegrityError(WorktreeError):
    pass


class State(str, Enum):
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    MERGED = "MERGED"
    DISCARDED = "DISCARDED"
    ORPHANED = "ORPHANED"
    RECOVERED = "RECOVERED"
    BLOCKED = "BLOCKED"


TRANSITIONS = {
    State.ALLOCATED: {State.ACTIVE, State.ORPHANED, State.BLOCKED},
    State.ACTIVE: {State.READY_FOR_REVIEW, State.ORPHANED, State.BLOCKED},
    State.READY_FOR_REVIEW: {State.MERGED, State.DISCARDED, State.ORPHANED, State.BLOCKED},
    State.ORPHANED: {State.RECOVERED, State.BLOCKED},
    State.RECOVERED: set(), State.MERGED: set(), State.DISCARDED: set(), State.BLOCKED: set(),
}


@dataclass(frozen=True)
class RepositoryIdentity:
    root: str
    canonical: str
    remote: str | None
    head: str
    ref: str | None

    @classmethod
    def from_root(cls, root: Path | str) -> "RepositoryIdentity":
        root = Path(root).resolve()
        fact = snapshot(root)
        if not fact.is_git or not fact.head:
            raise WorktreeError("source is not a usable Git repository")
        canonical = fact.identity + "@" + fact.head
        return cls(str(root), canonical, fact.remote, fact.head, fact.branch)


@dataclass
class WorktreeRecord:
    worktree_id: str
    repository: RepositoryIdentity
    path: str
    branch: str
    task_id: str
    owner: Principal
    source_head: str
    state: State = State.ALLOCATED
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    lease_until: str | None = None
    dirty_fingerprint: dict[str, str] = field(default_factory=dict)
    operation_ids: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)
    schema_version: str = "agentterm.worktree.v1"
    metadata_digest: str = ""

    def unsigned(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        value["repository"] = asdict(self.repository)
        value["owner"] = self.owner.as_dict()
        value.pop("metadata_digest", None)
        return value


@dataclass(frozen=True)
class Approval:
    operation_id: str
    operation: str
    worktree_id: str
    actor: Principal
    repository_canonical: str
    source_head: str
    target_ref: str | None
    review_digest: str | None
    created_at: str = field(default_factory=utc_now)

    def digest(self) -> str:
        return canonical_hash(asdict(self) | {"actor": self.actor.as_dict()})


class GitAdapter(Protocol):
    can_mutate: bool
    def create(self, source: Path, destination: Path, branch: str, head: str) -> None: ...
    def merge(self, source: Path, branch: str, target_ref: str) -> str: ...
    def discard(self, source: Path, destination: Path) -> None: ...
    def preview(self, source: Path, branch: str, target_ref: str) -> str: ...


def _run(args: list[str], cwd: Path, *, timeout: int = 30) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise WorktreeError((result.stderr or result.stdout or "git failed").strip()[:1000])
    return result.stdout.strip()


class ProductionGitAdapter:
    can_mutate = False
    def _deny(self) -> None:
        raise WorktreeError("production Git mutation is disabled pending independent approval")
    def create(self, source: Path, destination: Path, branch: str, head: str) -> None: self._deny()
    def merge(self, source: Path, branch: str, target_ref: str) -> str: self._deny()
    def discard(self, source: Path, destination: Path) -> None: self._deny()
    def preview(self, source: Path, branch: str, target_ref: str) -> str: self._deny()


class SyntheticGitAdapter:
    can_mutate = True
    def __init__(self, fixture_root: Path | str):
        self.fixture_root = Path(fixture_root).resolve()
        if not (self.fixture_root / ".git").exists():
            raise WorktreeError("synthetic adapter requires a disposable Git fixture")

    def _check(self, path: Path) -> None:
        path = path.resolve()
        if path != self.fixture_root and self.fixture_root not in path.parents:
            raise WorktreeError("synthetic path escaped fixture")

    def _destination_check(self, path: Path) -> None:
        path = path.resolve()
        if path == self.fixture_root or path.is_symlink():
            raise WorktreeError("invalid synthetic destination")

    def create(self, source: Path, destination: Path, branch: str, head: str) -> None:
        self._check(source); self._destination_check(destination)
        if destination.exists(): raise WorktreeError("worktree destination already exists")
        _run(["worktree", "add", "-b", branch, str(destination), head], source)

    def merge(self, source: Path, branch: str, target_ref: str) -> str:
        self._check(source)
        if target_ref not in {"main", "master"} and not target_ref.startswith("refs/heads/"):
            raise WorktreeError("synthetic merge target is not an explicit local ref")
        return _run(["merge", "--no-edit", branch], source)

    def discard(self, source: Path, destination: Path) -> None:
        self._check(source); self._destination_check(destination)
        _run(["worktree", "remove", "--force", str(destination)], source)

    def preview(self, source: Path, branch: str, target_ref: str) -> str:
        self._check(source)
        if target_ref not in {"main", "master"} and not target_ref.startswith("refs/heads/"):
            raise WorktreeError("synthetic merge target is not an explicit local ref")
        return _run(["merge-tree", "--write-tree", target_ref, branch], source)


class WorktreeManager:
    def __init__(self, app_root: Path | str, *, adapter: GitAdapter | None = None,
                 protected_roots: Iterable[Path | str] = (), ledger: Any | None = None):
        self.app_root = Path(app_root).resolve()
        self.app_root.mkdir(parents=True, exist_ok=True)
        self.worktrees_root = self.app_root / "worktrees"
        self.worktrees_root.mkdir(exist_ok=True)
        self.state_root = self.app_root / "state"
        self.state_root.mkdir(exist_ok=True)
        self.lock_path = self.state_root / "manager.lock"
        self.key_path = self.state_root / "metadata.key"
        if not self.key_path.exists():
            self.key_path.write_bytes(secrets.token_bytes(32)); os.chmod(self.key_path, 0o600)
        self.key = self.key_path.read_bytes()
        self.adapter = adapter or ProductionGitAdapter()
        self.protected = {Path(p).resolve() for p in protected_roots}
        self.ledger = ledger

    @contextlib.contextmanager
    def _lock(self):
        with self.lock_path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _path_safe(self, path: Path) -> None:
        candidate = path if path.is_absolute() else self.app_root / path
        try:
            relative = candidate.relative_to(self.app_root)
        except ValueError as exc:
            raise WorktreeError("worktree path is outside application root") from exc
        current = self.app_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise WorktreeError("symlink path component rejected")
        path = candidate.resolve()
        if path == self.app_root or self.app_root not in path.parents:
            raise WorktreeError("worktree path is outside application root")
        if any(path == p or p in path.parents for p in self.protected):
            raise WorktreeError("protected checkout cannot be a managed worktree")

    def _record_path(self, worktree_id: str) -> Path: return self.state_root / (worktree_id + ".json")

    def _save(self, record: WorktreeRecord) -> None:
        record.metadata_digest = hmac.new(self.key, canonical_bytes(record.unsigned()), hashlib.sha256).hexdigest()
        target = self._record_path(record.worktree_id); temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(record) | {"state": record.state.value, "repository": asdict(record.repository), "owner": record.owner.as_dict()}, sort_keys=True))
        os.replace(temp, target)

    def _load(self, worktree_id: str) -> WorktreeRecord:
        data = json.loads(self._record_path(worktree_id).read_text())
        digest = data.pop("metadata_digest", "")
        data["repository"] = RepositoryIdentity(**data["repository"])
        data["owner"] = Principal(**data["owner"])
        data["state"] = State(data["state"])
        record = WorktreeRecord(**data)
        if not hmac.compare_digest(digest, hmac.new(self.key, canonical_bytes(record.unsigned()), hashlib.sha256).hexdigest()):
            raise IntegrityError("worktree metadata authentication failed")
        record.metadata_digest = digest
        return record

    def _authorize(self, actor: Principal | None, operation: str, resource: str, grants: Iterable[Grant]) -> None:
        decision = authorize(actor, operation, resource, grants)
        if not decision.allowed: raise AuthorizationError(decision.reason)

    def _audit(self, operation: str, resource: str, actor: Principal, result: str, provenance: dict[str, str]) -> str:
        receipt = AuditReceipt(uuid.uuid4().hex, uuid.uuid4().hex, actor, operation, resource,
                               authorize(actor, operation, resource, [Grant(actor, operation, resource)]), result,
                               redact_obj(provenance), created_at=utc_now())
        if self.ledger:
            self.ledger.append("agentterm", "worktree_" + operation, receipt.as_dict())
        return receipt.digest()

    def create(self, source: Path | str, *, task_id: str, owner: Principal, grants: Iterable[Grant],
               lease_until: str | None = None) -> WorktreeRecord:
        self._authorize(owner, "worktree.create", "repository", grants)
        if not self.adapter.can_mutate: raise WorktreeError("worktree creation disabled by fail-closed adapter")
        source = Path(source).resolve(); identity = RepositoryIdentity.from_root(source)
        worktree_id = "wt-" + uuid.uuid4().hex
        destination = self.worktrees_root / worktree_id; self._path_safe(destination)
        record = WorktreeRecord(worktree_id, identity, str(destination), "agentterm/" + worktree_id,
                                task_id, owner, identity.head, lease_until=lease_until)
        with self._lock():
            self.adapter.create(source, destination, record.branch, record.source_head)
            record.state = State.ACTIVE; record.updated_at = utc_now(); self._save(record)
        record.receipts.append(self._audit("create", worktree_id, owner, "created", {"repository": identity.canonical, "source_head": identity.head}))
        with self._lock(): self._save(record)
        return record

    def get(self, worktree_id: str) -> WorktreeRecord: return self._load(worktree_id)

    def admit_repository(self, source: Path | str) -> RepositoryIdentity:
        """Read-only admission check; it never creates or changes Git state."""
        source = Path(source).resolve()
        if source == self.app_root or self.app_root in source.parents:
            raise WorktreeError("application state root cannot be admitted as a source repository")
        return RepositoryIdentity.from_root(source)

    def status(self, worktree_id: str) -> dict[str, Any]:
        record = self._load(worktree_id); fact = snapshot(record.path)
        if not fact.is_git or fact.identity != record.repository.remote and record.repository.remote is not None:
            raise IntegrityError("managed worktree repository identity changed")
        return {"worktree_id": record.worktree_id, "state": record.state.value, "path": record.path,
                "branch": fact.branch, "head": fact.head, "dirty": fact.dirty,
                "dirty_paths": list(fact.dirty_paths), "lease_until": record.lease_until}

    def preview_merge(self, worktree_id: str, target_ref: str = "main") -> str:
        record = self._load(worktree_id)
        if record.state != State.READY_FOR_REVIEW: raise WorktreeError("merge preview requires READY_FOR_REVIEW")
        return self.adapter.preview(Path(record.repository.root), record.branch, target_ref)

    def archive(self, worktree_id: str, destination: Path | str) -> Path:
        """Copy evidence without deleting or changing the managed worktree."""
        record = self._load(worktree_id); target = Path(destination).resolve(); self._path_safe(target)
        if target.exists(): raise WorktreeError("archive destination already exists")
        shutil.copytree(record.path, target, symlinks=False)
        return target

    def transition(self, worktree_id: str, state: State) -> WorktreeRecord:
        with self._lock():
            record = self._load(worktree_id)
            if state not in TRANSITIONS[record.state]: raise WorktreeError(f"invalid transition {record.state}->{state}")
            record.state = state; record.updated_at = utc_now(); self._save(record); return record

    def approve(self, worktree_id: str, *, operation: str, actor: Principal, grants: Iterable[Grant],
                target_ref: str | None = None, review_digest: str | None = None) -> Approval:
        self._authorize(actor, "worktree." + operation, worktree_id, grants)
        record = self._load(worktree_id)
        if record.owner != actor: raise AuthorizationError("approval actor is not worktree owner")
        if operation not in {"merge", "discard"}: raise WorktreeError("approval operation is not mutable")
        if operation == "merge" and record.state != State.READY_FOR_REVIEW: raise WorktreeError("merge requires READY_FOR_REVIEW")
        if operation == "discard" and record.state not in {State.ACTIVE, State.READY_FOR_REVIEW, State.ORPHANED}: raise WorktreeError("discard is not valid for this state")
        return Approval(uuid.uuid4().hex, operation, worktree_id, actor, record.repository.canonical,
                        record.source_head, target_ref, review_digest)

    def merge(self, approval: Approval) -> WorktreeRecord:
        return self._mutate_approved(approval, "merge")

    def discard(self, approval: Approval) -> WorktreeRecord:
        return self._mutate_approved(approval, "discard")

    def _mutate_approved(self, approval: Approval, operation: str) -> WorktreeRecord:
        if approval.operation != operation: raise AuthorizationError("approval operation mismatch")
        with self._lock():
            record = self._load(approval.worktree_id)
            if record.repository.canonical != approval.repository_canonical or record.source_head != approval.source_head:
                raise IntegrityError("approval binding no longer matches repository")
            if approval.operation_id in record.operation_ids: raise WorktreeError("approval replay rejected")
            source, destination = Path(record.repository.root), Path(record.path)
            if operation == "merge":
                if record.state != State.READY_FOR_REVIEW: raise WorktreeError("merge requires review state")
                self.adapter.merge(source, record.branch, approval.target_ref or "main"); new_state = State.MERGED
            else:
                self.adapter.discard(source, destination); new_state = State.DISCARDED
            record.operation_ids.append(approval.operation_id); record.state = new_state; record.updated_at = utc_now(); self._save(record)
            record.receipts.append(self._audit(operation, record.worktree_id, approval.actor, new_state.value.lower(), {"approval": approval.digest()})); self._save(record)
            return record

    def recover(self) -> list[WorktreeRecord]:
        results = []
        with self._lock():
            for path in sorted(self.state_root.glob("wt-*.json")):
                try: record = self._load(path.stem)
                except Exception: continue
                if record.state in {State.ACTIVE, State.ALLOCATED, State.READY_FOR_REVIEW} and not Path(record.path).exists():
                    record.state = State.ORPHANED; record.updated_at = utc_now(); self._save(record)
                results.append(record)
            known = {Path(r.path).resolve() for r in results}
            for child in self.worktrees_root.iterdir():
                if child.resolve() not in known:
                    # Unknown content is never deleted; it is reported only.
                    results.append(WorktreeRecord("unknown-" + child.name, RepositoryIdentity(str(child), "unknown", None, "unknown", None), str(child), "unknown", "unknown", Principal("unknown", "unknown", "unknown", "unknown"), "unknown", State.BLOCKED))
        return results


def run_in_worktree(record: WorktreeRecord, command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Launch a bounded process in the assigned path; never inherit a caller cwd."""
    path = Path(record.path).resolve()
    if not path.is_dir() or record.state not in {State.ACTIVE, State.READY_FOR_REVIEW}:
        raise WorktreeError("worktree is not active")
    safe_env = {"PATH": os.environ.get("PATH", ""), "HOME": str(path), "AGENTTERM_WORKTREE_ID": record.worktree_id}
    if env: safe_env.update({k: v for k, v in env.items() if k not in {"PWD", "OLDPWD"}})
    return subprocess.run(command, cwd=str(path), env=safe_env, capture_output=True, text=True, timeout=60)
