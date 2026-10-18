#!/usr/bin/env python3
"""Discover Bootstrap's optional tools without installing or mutating anything."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tooling" / "bootstrap_tools.json"
MCP_REGISTRATION = ROOT / "tooling" / "mcp.registration.json"


def _command_version(command: str, args: list[str]) -> str | None:
    executable = shutil.which(command)
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *args], check=False, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return "PRESENT_BUT_VERSION_CHECK_FAILED"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else "PRESENT"


def _mcp_registration() -> dict[str, Any]:
    try:
        registration = json.loads(MCP_REGISTRATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"valid": False, "reason": f"registration unreadable: {error}"}
    servers = registration.get("mcpServers")
    if not isinstance(servers, dict):
        return {"valid": False, "reason": "mcpServers must be an object"}
    for name, entry in servers.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            return {"valid": False, "reason": "each MCP entry must be an object"}
        if not isinstance(entry.get("command"), str) or not isinstance(entry.get("args"), list):
            return {"valid": False, "reason": f"invalid MCP entry: {name}"}
        if not all(isinstance(item, str) for item in entry["args"]):
            return {"valid": False, "reason": f"MCP args must be strings: {name}"}
    return {"valid": True, "servers": sorted(servers)}


def _active_codex_mcp_registration(name: str, config_path: Path | None = None) -> bool:
    path = config_path or (Path.home() / ".codex" / "config.toml")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return f"[mcp_servers.{name}]" in text


def discover(tool_root: Path | None = None) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registration = _mcp_registration()
    terminal_app = Path("/System/Applications/Utilities/Terminal.app")
    results: list[dict[str, Any]] = []
    for tool in manifest["tools"]:
        tool_id = tool["id"]
        evidence: dict[str, Any] = {
            "upstream": tool.get("upstream"),
            "kind": tool["kind"],
            "registered": False,
            "available": False,
            "operational": False,
        }
        status = "NOT_INSTALLED"
        if tool_id == "agentterm":
            isolated_bin = tool_root / "install" / "agentterm-venv" / "bin" / "agentterm" if tool_root else None
            command = str(isolated_bin) if isolated_bin and isolated_bin.exists() else "agentterm"
            version = _command_version(command, ["--version"])
            evidence["source"] = tool.get("source")
            evidence["archive_sha256"] = tool.get("archive_sha256")
            evidence["installation_root"] = str(tool_root) if isolated_bin and isolated_bin.exists() else None
            evidence["version"] = version
            if version is not None:
                evidence["available"] = True
                try:
                    health = subprocess.run(
                        [command, "--help"], check=False, capture_output=True, text=True, timeout=5
                    )
                    evidence["operational"] = health.returncode == 0 and "governed" in (health.stdout or "").lower()
                except (OSError, subprocess.TimeoutExpired):
                    evidence["operational"] = False
            status = "AVAILABLE" if evidence["operational"] else "NOT_INSTALLED"
        elif tool_id == "open-terminal":
            evidence["terminal_app_present"] = terminal_app.exists()
            evidence["osascript_present"] = shutil.which("osascript") is not None
            evidence["managed_pty_bridge"] = (ROOT / "scripts" / "open_terminal_bridge.py").is_file()
            evidence["supported_modes"] = ["managed_pty", "native_terminal_new_tab"]
            evidence["unsupported_modes"] = ["arbitrary_existing_tab_attach", "native_output_capture"]
            evidence["reason"] = "native new-tab launch and managed PTY are supported; arbitrary existing-tab control is not"
            evidence["available"] = bool(evidence["terminal_app_present"] and evidence["osascript_present"] and evidence["managed_pty_bridge"])
            evidence["operational"] = evidence["available"]
            status = "AVAILABLE" if evidence["available"] else "BLOCKED"
        elif tool_id == "api-anything":
            isolated_bin = tool_root / "install" / "api-anything" / "node_modules" / ".bin" / "api-anything" if tool_root else None
            command = str(isolated_bin) if isolated_bin and isolated_bin.exists() else "api-anything"
            version = _command_version(command, ["--version"])
            evidence["version"] = version
            evidence["installation_root"] = str(tool_root) if isolated_bin and isolated_bin.exists() else None
            evidence["local_registration"] = registration.get("valid") and tool_id in registration.get("servers", [])
            evidence["active_codex_registration"] = _active_codex_mcp_registration(tool_id)
            if version is not None:
                evidence["available"] = True
                try:
                    health = subprocess.run(
                        [command, "--help"], check=False, capture_output=True, text=True, timeout=5
                    )
                    evidence["operational"] = health.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    evidence["operational"] = False
            if evidence["operational"]:
                status = "AVAILABLE" if evidence["active_codex_registration"] else "NOT_REGISTERED"
            else:
                status = "NOT_INSTALLED"
        elif tool_id == "mirofish":
            evidence["expected_entrypoint"] = "upstream application; no CLI/MCP command asserted"
            checkout = tool_root / "src" / "MiroFish" if tool_root else None
            evidence["local_checkout"] = bool(checkout and checkout.is_dir())
            evidence["frontend_build"] = bool(checkout and (checkout / "frontend" / "dist").is_dir())
            uv_command = tool_root / "install" / "mirofish-uv" / "bin" / "uv" if tool_root else None
            python_command = tool_root / "install" / "mirofish-uv" / "bin" / "python" if tool_root else None
            uv_executable = str(uv_command) if uv_command and uv_command.exists() else "uv"
            python_executable = str(python_command) if python_command and python_command.exists() else "python3"
            evidence["uv"] = _command_version(uv_executable, ["--version"])
            evidence["uv_available"] = evidence["uv"] is not None
            evidence["python"] = _command_version(python_executable, ["--version"])
            evidence["python_supported"] = evidence["python"] is not None and any(
                f"Python 3.{minor}." in evidence["python"] for minor in (11, 12)
            )
            lockfile = checkout / "backend" / "uv.lock" if checkout else None
            evidence["backend_lock_present"] = bool(lockfile and lockfile.is_file())
            evidence["backend_environment"] = bool(checkout and (checkout / "backend" / ".venv").is_dir())
            evidence["platform_machine"] = platform.machine()
            torch_platform_block = bool(
                evidence["backend_lock_present"]
                and evidence["python_supported"]
                and platform.system() == "Darwin"
                and platform.machine() == "x86_64"
                and "name = \"torch\"" in lockfile.read_text(encoding="utf-8", errors="replace")
                and "version = \"2.9.1\"" in lockfile.read_text(encoding="utf-8", errors="replace")
            )
            if torch_platform_block:
                status = "INCOMPATIBLE"
                evidence["reason"] = "MiroFish lock pins torch 2.9.1, which has no macOS x86_64 wheel"
            elif evidence["local_checkout"] and evidence["frontend_build"] and not evidence["uv_available"]:
                status = "INCOMPATIBLE"
                evidence["reason"] = "uv is unavailable"
        elif tool_id == "loadersz-core":
            evidence["expected_entrypoint"] = "npm package: loadersz"
            evidence["node"] = _command_version("node", ["--version"])
            package_root = tool_root / "src" / "loadersz-core" if tool_root else None
            evidence["npm_package_probe"] = "NOT_RUN (discovery is read-only and package is project-specific)"
            evidence["installation_root"] = str(tool_root) if package_root and package_root.is_dir() else None
            if package_root and (package_root / "node_modules").is_dir() and (package_root / "dist").is_dir():
                evidence["available"] = True
                evidence["operational"] = True
                status = "AVAILABLE"
        results.append({"id": tool_id, "name": tool["name"], "status": status, "evidence": evidence})
    return {
        "schema_version": "bootstrap_tool_discovery.v1",
        "platform": platform.platform(),
        "root": str(ROOT),
        "mcp_registration": registration,
        "tools": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON (default and compatibility flag)")
    parser.add_argument(
        "--tool-root",
        type=Path,
        default=Path(os.environ["CODEX_BOOTSTRAP_TOOL_ROOT"]).expanduser()
        if os.environ.get("CODEX_BOOTSTRAP_TOOL_ROOT") else None,
        help="optional isolated provisioning root; never installed or modified by discovery",
    )
    args = parser.parse_args(argv)
    print(json.dumps(discover(args.tool_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
