"""Read-only Git facts: identity, HEAD, branch, dirty state, worktree fingerprints."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

INTERNAL_DIR = ".agentterm"


def _git(args: list[str], cwd: Path | str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def normalize_remote(url: str) -> str:
    """Collapse ssh/https/scp-style remotes (and strip credentials) to one identity."""
    value = url.strip()
    scp = re.match(r"^[\w.\-]+@([\w.\-]+):(.+)$", value)
    if scp:
        host, path = scp.groups()
        value = f"https://{host}/{path}"
    else:
        url_form = re.match(r"^\w+://(?:[^@/]+@)?([^/]+)/(.+)$", value)
        if url_form:
            host, path = url_form.groups()
            value = f"https://{host}/{path}"
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


@dataclass(frozen=True)
class Snapshot:
    root: str
    is_git: bool
    identity: str
    remote: str | None
    head: str | None
    branch: str | None
    dirty: bool
    dirty_paths: tuple[str, ...]

    def as_dict(self) -> dict:
        data = asdict(self)
        data["dirty_paths"] = list(self.dirty_paths)
        return data

    @property
    def worktree_state(self) -> str:
        if not self.is_git:
            return "UNKNOWN"
        return "DIRTY" if self.dirty else "CLEAN"


def repo_root(cwd: Path | str) -> Path | None:
    out = _git(["rev-parse", "--show-toplevel"], cwd)
    if out and out.strip():
        return Path(out.strip())
    return None


def _porcelain_paths(cwd: Path | str) -> list[str] | None:
    out = _git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd)
    if out is None:
        return None
    entries = out.split("\0")
    paths: list[str] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # the following entry is the rename source
        if path.startswith(INTERNAL_DIR + "/") or path == INTERNAL_DIR:
            continue
        paths.append(path)
    return sorted(set(paths))


def snapshot(cwd: Path | str) -> Snapshot:
    cwd = Path(cwd).resolve()
    root = repo_root(cwd)
    if root is None:
        digest = hashlib.sha1(str(cwd).encode()).hexdigest()[:12]
        return Snapshot(str(cwd), False, f"local:{digest}", None, None, None, False, ())
    remote_raw = _git(["remote", "get-url", "origin"], root)
    remote = normalize_remote(remote_raw) if remote_raw and remote_raw.strip() else None
    head_raw = _git(["rev-parse", "HEAD"], root)
    head = head_raw.strip() if head_raw and head_raw.strip() else None
    branch_raw = _git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    branch = branch_raw.strip() if branch_raw and branch_raw.strip() else None
    paths = _porcelain_paths(root) or []
    identity = remote or "local:" + hashlib.sha1(str(root).encode()).hexdigest()[:12]
    return Snapshot(str(root), True, identity, remote, head, branch, bool(paths), tuple(paths))


def _hash_file(path: Path) -> str:
    if path.is_dir():
        return "<dir>"
    if not path.exists():
        return "<absent>"
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return "<unreadable>"
    return digest.hexdigest()


def worktree_fingerprint(root: Path | str) -> dict[str, str]:
    """Map every dirty/untracked path to its content hash (``.agentterm`` excluded)."""
    root = Path(root)
    paths = _porcelain_paths(root) or []
    return {p: _hash_file(root / p) for p in paths}


def changed_paths(
    root: Path | str,
    before: dict[str, str],
    after: dict[str, str],
    head_before: str | None,
    head_after: str | None,
) -> list[str]:
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    if head_before and head_after and head_before != head_after:
        out = _git(["diff", "--name-only", f"{head_before}", f"{head_after}"], root)
        if out:
            changed.update(line for line in out.splitlines() if line.strip())
    return sorted(p for p in changed if not p.startswith(INTERNAL_DIR + "/"))


def diff_text(root: Path | str, base: str | None = None, head: str | None = None,
              max_chars: int = 20_000) -> str:
    """Unified diff for review: ``base..head`` when given, else the worktree against HEAD."""
    args = ["diff", "--no-color"]
    if base and head:
        args += [base, head]
    elif base:
        args += [base]
    else:
        args += ["HEAD"]
    out = _git(args, root) or ""
    untracked = [p for p in (_porcelain_paths(root) or []) if not (Path(root) / p).is_dir()]
    new_files = _git(["ls-files", "--others", "--exclude-standard"], root) or ""
    names = [n for n in new_files.splitlines() if n.strip() and n in untracked]
    if names and not (base and head):
        out += "\n# untracked files (contents not shown): " + ", ".join(names[:50]) + "\n"
    if len(out) > max_chars:
        out = out[:max_chars] + "\n# [diff truncated to fit the context budget]\n"
    return out


def user_identity(cwd: Path | str) -> str:
    import getpass

    out = _git(["config", "user.email"], cwd)
    if out and out.strip():
        return out.strip()
    try:
        return getpass.getuser()
    except Exception:  # pragma: no cover - platform specific
        return "unknown-user"
