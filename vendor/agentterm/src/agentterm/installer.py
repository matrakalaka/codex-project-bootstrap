"""Manifest-driven tool discovery and installation.

Follows the DISCOVER -> CLASSIFY -> REUSE -> IDENTIFY GAP -> PROPOSE -> APPROVE -> QUALIFY
flow from codex-project-bootstrap. Discovery is read-only. Nothing is installed unless the
person passes ``--apply`` (and confirms). Global agent configuration is never edited; MCP
servers are written to the project-local ``.mcp.json`` only.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ALREADY_HAVE = "ALREADY_HAVE"
REAL_GAP = "REAL_GAP"
OPTIONAL = "OPTIONAL"
BLOCKED = "BLOCKED_PRECONDITION"

_PREFERENCE = {
    "darwin": ("brew", "npm", "pipx", "pip", "cargo", "cmd"),
    "win32": ("winget", "npm", "pipx", "pip", "cargo", "cmd"),
    "linux": ("npm", "pipx", "pip", "brew", "cargo", "cmd"),
}


@dataclass
class ToolStatus:
    id: str
    kind: str
    required: bool
    classification: str
    version: str | None = None
    detail: str = ""
    manager: str | None = None
    argv: list[str] | None = None
    env_missing: list[str] = field(default_factory=list)
    mcp: dict[str, Any] | None = None

    @property
    def action(self) -> str:
        if self.manager == "mcp-json":
            return "write .mcp.json entry"
        return shlex.join(self.argv) if self.argv else "-"


def _argv_for(manager: str, spec: Any) -> list[str]:
    if manager == "npm":
        return ["npm", "install", "-g", str(spec)]
    if manager == "pipx":
        return ["pipx", "install", str(spec)]
    if manager == "pip":
        return [sys.executable, "-m", "pip", "install", "--user", str(spec)]
    if manager == "brew":
        return ["brew", "install", str(spec)]
    if manager == "winget":
        return ["winget", "install", "--id", str(spec), "-e", "--accept-source-agreements"]
    if manager == "cargo":
        return ["cargo", "install", str(spec)]
    if manager == "cmd":
        return [str(part) for part in spec]
    raise ValueError(f"unknown install method {manager!r}")


def pick_method(install: dict[str, Any], platform: str, which: Callable[[str], str | None]) -> tuple[str, list[str]] | None:
    order = _PREFERENCE.get(platform if platform in _PREFERENCE else "linux")
    for manager in order:
        if manager not in install:
            continue
        argv = _argv_for(manager, install[manager])
        exe = argv[0]
        if manager == "pip" or which(exe):
            return manager, argv
    return None


def _check(tool: dict[str, Any], which: Callable[[str], str | None]) -> tuple[bool, str | None]:
    command = tool.get("check")
    if not command:
        found = which(tool["id"])
        return bool(found), None
    try:
        argv = shlex.split(command) if isinstance(command, str) else list(command)
        if not which(argv[0]):
            return False, None
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError, ValueError):
        return False, None
    if r.returncode != 0:
        return False, None
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return True, out[0] if out else None


def _mcp_present(root: Path, tool_id: str) -> bool:
    path = root / ".mcp.json"
    if not path.exists():
        return False
    try:
        return tool_id in json.loads(path.read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, json.JSONDecodeError):
        return False


def discover(manifest: dict[str, Any], root: Path, *, platform: str = sys.platform,
             which: Callable[[str], str | None] = shutil.which) -> list[ToolStatus]:
    statuses: list[ToolStatus] = []
    for tool in manifest.get("tool", []):
        tid = str(tool["id"])
        kind = str(tool.get("kind", "cli"))
        required = bool(tool.get("required", False))
        missing_env = [name for name in tool.get("env", []) if not os.environ.get(name)]
        if kind == "mcp":
            spec = tool.get("mcp")
            if not isinstance(spec, dict) or "command" not in spec:
                statuses.append(ToolStatus(tid, kind, required, BLOCKED, detail="mcp entry needs [tool.mcp] with a command"))
                continue
            if _mcp_present(root, tid):
                statuses.append(ToolStatus(tid, kind, required, ALREADY_HAVE, detail=".mcp.json", env_missing=missing_env, mcp=spec))
            else:
                statuses.append(ToolStatus(tid, kind, required, REAL_GAP if required else OPTIONAL, manager="mcp-json",
                                           detail="project-local .mcp.json", env_missing=missing_env, mcp=spec))
            continue
        present, version = _check(tool, which)
        if present:
            statuses.append(ToolStatus(tid, kind, required, ALREADY_HAVE, version=version, env_missing=missing_env))
            continue
        method = pick_method(tool.get("install", {}), platform, which)
        if method is None:
            statuses.append(ToolStatus(tid, kind, required, BLOCKED if required else OPTIONAL,
                                       detail="no usable installer for this platform (install it manually)",
                                       env_missing=missing_env))
        else:
            manager, argv = method
            statuses.append(ToolStatus(tid, kind, required, REAL_GAP if required else OPTIONAL,
                                       manager=manager, argv=argv, env_missing=missing_env))
    return statuses


def render_plan(statuses: list[ToolStatus]) -> str:
    if not statuses:
        return "No [[tool]] entries in the manifest."
    rows = [("TOOL", "KIND", "CLASSIFICATION", "DETAIL / PLANNED ACTION")]
    for s in statuses:
        detail = s.version or s.detail
        if s.classification in (REAL_GAP, OPTIONAL) and s.manager:
            detail = s.action
        if s.env_missing:
            detail += f"  [env missing: {', '.join(s.env_missing)}]"
        rows.append((s.id, s.kind, s.classification + ("" if s.required else " (optional)" if s.classification != ALREADY_HAVE else ""), detail))
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    return "\n".join(f"{r[0]:<{widths[0]}}  {r[1]:<{widths[1]}}  {r[2]:<{widths[2]}}  {r[3]}" for r in rows)


def write_mcp_json(root: Path, tool: ToolStatus) -> None:
    path = root / ".mcp.json"
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    servers = data.setdefault("mcpServers", {})
    spec = tool.mcp or {}
    entry: dict[str, Any] = {"command": spec["command"], "args": list(spec.get("args", []))}
    if spec.get("env"):
        entry["env"] = {name: f"${{{name}}}" for name in spec["env"]}
    servers[tool.id] = entry
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@dataclass
class InstallResult:
    id: str
    ok: bool
    detail: str


def apply(statuses: list[ToolStatus], root: Path, *, include_optional: bool = False,
          only: list[str] | None = None, which: Callable[[str], str | None] = shutil.which,
          runner: Callable[..., Any] = subprocess.run) -> list[InstallResult]:
    """Install the planned gaps. Stops at the first failure."""
    results: list[InstallResult] = []
    for s in statuses:
        wanted = (s.id in only) if only else (s.classification == REAL_GAP or (include_optional and s.classification == OPTIONAL))
        if not wanted or s.classification == ALREADY_HAVE:
            continue
        if s.manager == "mcp-json":
            write_mcp_json(root, s)
            results.append(InstallResult(s.id, True, "wrote .mcp.json"))
            continue
        if not s.argv:
            results.append(InstallResult(s.id, False, s.detail or "no installer available"))
            break
        try:
            r = runner(s.argv, capture_output=True, text=True, timeout=1800)
        except (OSError, subprocess.SubprocessError) as exc:
            results.append(InstallResult(s.id, False, str(exc)))
            break
        if r.returncode != 0:
            tail = ((r.stderr or "") + (r.stdout or ""))[-400:].strip()
            results.append(InstallResult(s.id, False, f"exit {r.returncode}: {tail}"))
            break
        results.append(InstallResult(s.id, True, "installed (re-run `agentterm init` to qualify)"))
    return results
