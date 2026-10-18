#!/usr/bin/env python3
"""Governed managed-PTY and native Terminal.app bridge for Bootstrap.

Managed sessions are the reliable interface: each session has a private Unix
socket, a dedicated zsh process, deterministic command submission, output and
exit-status capture, and no dependence on the active Terminal window. Native
mode is deliberately narrower: it opens a new Terminal.app tab via AppleScript
and cannot attach to an arbitrary existing tab or capture its output.
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import re
import secrets
import select
import signal
import socket
import subprocess
import sys
import termios
import time
from pathlib import Path
from typing import Any


class TerminalBridgeError(RuntimeError):
    pass


SESSION_SCHEMA = "bootstrap_terminal_session.v1"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
_PROCESS_HANDLES: dict[str, subprocess.Popen[bytes]] = {}


def _session_dir(project_root: Path) -> Path:
    return project_root / ".agentterm" / "terminal-sessions"


def _metadata_path(project_root: Path, session_id: str) -> Path:
    if not _ID_RE.fullmatch(session_id):
        raise TerminalBridgeError("invalid terminal session id")
    return _session_dir(project_root) / f"{session_id}.json"


def _socket_path(project_root: Path, session_id: str) -> Path:
    # macOS AF_UNIX paths are short; project-scoped metadata may live in a
    # deeply nested temporary checkout, so keep the live socket in TMPDIR.
    return Path("/tmp") / f"codex-bootstrap-terminal-{session_id}.sock"


def _write_metadata(path: Path, body: dict[str, Any]) -> None:
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_metadata(project_root: Path, session_id: str) -> dict[str, Any]:
    path = _metadata_path(project_root, session_id)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TerminalBridgeError(f"terminal session metadata unavailable: {exc}") from exc
    if body.get("schema") != SESSION_SCHEMA or body.get("project_root") != str(project_root.resolve()):
        raise TerminalBridgeError("terminal session is not bound to this project")
    return body


def _native_osascript(command: str) -> str:
    script = """
on run argv
  set commandText to item 1 of argv
  tell application \"Terminal\"
    activate
    set newTab to do script commandText
    set targetWindow to window 1
    return (id of targetWindow as text)
  end tell
end run
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script, "--", command],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TerminalBridgeError(f"native Terminal.app automation unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise TerminalBridgeError(f"native Terminal.app automation denied or failed: {detail}")
    return result.stdout.strip()


def open_session(project_root: Path, *, mode: str, approved: bool, command: str = "") -> dict[str, Any]:
    root = project_root.resolve()
    if not approved:
        raise TerminalBridgeError("explicit owner approval is required before opening a terminal session")
    if not root.is_dir():
        raise TerminalBridgeError("terminal project root does not exist")
    if mode not in {"managed", "native"}:
        raise TerminalBridgeError("terminal mode must be managed or native")
    session_id = f"terminal-{secrets.token_hex(16)}"
    directory = _session_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": SESSION_SCHEMA, "session_id": session_id,
        "project_root": str(root), "mode": mode, "state": "STARTING",
        "created_at": time.time(), "output_capture": mode == "managed",
    }
    metadata_path = _metadata_path(root, session_id)
    if mode == "native":
        metadata["native_window_id"] = _native_osascript(command)
        metadata["state"] = "OPEN"
        metadata["limitation"] = "new-tab launch only; arbitrary existing-tab input and output capture unsupported"
        _write_metadata(metadata_path, metadata)
        return metadata

    sock = _socket_path(root, session_id)
    metadata["socket"] = str(sock)
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--serve", "--socket", str(sock), "--project-root", str(root)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _PROCESS_HANDLES[session_id] = process
    metadata["pid"] = process.pid
    _write_metadata(metadata_path, metadata)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if sock.exists():
            try:
                with _connect(sock) as client:
                    _request(client, {"type": "ping"})
                metadata["state"] = "OPEN"
                _write_metadata(metadata_path, metadata)
                return metadata
            except (OSError, TerminalBridgeError):
                pass
        time.sleep(0.02)
    metadata["state"] = "FAILED"
    _write_metadata(metadata_path, metadata)
    process.terminate()
    process.wait(timeout=2)
    _PROCESS_HANDLES.pop(session_id, None)
    raise TerminalBridgeError("managed terminal session did not become ready")


def _connect(sock: Path) -> socket.socket:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    client.connect(str(sock))
    return client


def _request(client: socket.socket, body: dict[str, Any]) -> dict[str, Any]:
    client.sendall((json.dumps(body, sort_keys=True) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = client.recv(65536)
        if not chunk:
            raise TerminalBridgeError("terminal session disconnected")
        data += chunk
    result = json.loads(data.decode())
    if result.get("outcome") == "BLOCKED_PRECONDITION":
        raise TerminalBridgeError(result.get("reason", "terminal operation blocked"))
    return result


def submit(project_root: Path, session_id: str, text: str, *, approved: bool, timeout: float = 10) -> dict[str, Any]:
    if not approved:
        raise TerminalBridgeError("explicit owner approval is required before sending terminal input")
    if not isinstance(text, str) or not text.strip():
        raise TerminalBridgeError("terminal input must be non-empty text")
    metadata = _load_metadata(project_root.resolve(), session_id)
    if metadata.get("mode") != "managed" or metadata.get("state") != "OPEN":
        raise TerminalBridgeError("only an open managed session accepts deterministic input")
    sock = Path(metadata["socket"])
    try:
        with _connect(sock) as client:
            return _request(client, {"type": "submit", "text": text, "timeout": min(max(timeout, 0.1), 30)})
    except OSError as exc:
        raise TerminalBridgeError(f"managed terminal session unavailable: {exc}") from exc


def close_session(project_root: Path, session_id: str, *, approved: bool) -> dict[str, Any]:
    if not approved:
        raise TerminalBridgeError("explicit owner approval is required before closing a terminal session")
    metadata = _load_metadata(project_root.resolve(), session_id)
    if metadata.get("mode") == "managed":
        try:
            with _connect(Path(metadata["socket"])) as client:
                result = _request(client, {"type": "close"})
        except OSError as exc:
            result = {"outcome": "FAILED_AFTER_EXECUTION", "reason": str(exc)}
    else:
        return {"outcome": "BLOCKED_PRECONDITION", "reason": "native Terminal.app window close is not supported by this bridge", "session_id": session_id}
    metadata["state"] = "CLOSED"
    metadata["closed_at"] = time.time()
    _write_metadata(_metadata_path(project_root.resolve(), session_id), metadata)
    handle = _PROCESS_HANDLES.pop(session_id, None)
    if handle is not None:
        try:
            handle.wait(timeout=2)
        except subprocess.TimeoutExpired:
            handle.terminate()
            handle.wait(timeout=2)
    return {**result, "session_id": session_id}


def _serve(sock_path: Path, project_root: Path) -> int:
    try:
        sock_path.unlink()
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(1)
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(project_root)
        os.environ["PS1"] = "__BOOTSTRAP_READY__%# "
        os.environ["PROMPT"] = "__BOOTSTRAP_READY__%# "
        os.execv("/bin/zsh", ["zsh", "-f", "-i"])
    # Drain the startup prompt before accepting input; otherwise the first
    # reviewed command can race shell initialization and be misclassified.
    startup = bytearray()
    deadline = time.monotonic() + 2
    while b"__BOOTSTRAP_READY__" not in startup and time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if ready:
            try:
                startup.extend(os.read(fd, 4096))
            except OSError:
                break
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except termios.error:
        pass
    try:
        while True:
            client, _ = server.accept()
            with client:
                line = client.makefile("r", encoding="utf-8").readline()
                if not line:
                    continue
                request = json.loads(line)
                if request.get("type") == "ping":
                    response = {"outcome": "PASS", "state": "OPEN"}
                elif request.get("type") == "submit":
                    response = _serve_submit(fd, request["text"], float(request.get("timeout", 10)))
                elif request.get("type") == "close":
                    os.write(fd, b"exit\n")
                    response = {"outcome": "PASS"}
                    client.sendall((json.dumps(response) + "\n").encode())
                    return 0
                else:
                    response = {"outcome": "BLOCKED_PRECONDITION", "reason": "unknown terminal request"}
                client.sendall((json.dumps(response, sort_keys=True) + "\n").encode())
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass
        server.close()
        try:
            sock_path.unlink()
        except FileNotFoundError:
            pass


def _serve_submit(fd: int, text: str, timeout: float) -> dict[str, Any]:
    token = "__BOOTSTRAP_STATUS_" + secrets.token_hex(8) + "__"
    split = len(token) // 2
    token_left, token_right = token[:split], token[split:]
    # Split the sentinel in the submitted text so a terminal driver's echoed
    # input cannot be mistaken for the command's actual completion record.
    payload = text.rstrip("\n") + (
        f"\nprintf '%s%s:%s\\n' '{token_left}' '{token_right}' $?\n"
    )
    os.write(fd, payload.encode())
    deadline = time.monotonic() + min(max(timeout, 0.1), 30)
    output = bytearray()
    marker = (token + ":").encode()
    while time.monotonic() < deadline:
        remaining = max(0.05, deadline - time.monotonic())
        ready, _, _ = select.select([fd], [], [], min(remaining, 0.25))
        if not ready:
            continue
        try:
            output.extend(os.read(fd, 65536))
        except OSError:
            break
        if marker in output:
            break
    if marker not in output:
        return {"outcome": "FAILED_AFTER_EXECUTION", "reason": "terminal command timed out", "output": output.decode(errors="replace")[-20000:]}
    raw = bytes(output)
    before, after = raw.rsplit(marker, 1)
    status_line = after.splitlines()[0].strip() if after.splitlines() else b"1"
    try:
        status = int(status_line)
    except ValueError:
        status = 1
    return {"outcome": "PASS" if status == 0 else "FAILED_AFTER_EXECUTION", "returncode": status,
            "output": before.decode(errors="replace")[-20000:]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args(argv)
    if args.serve and args.socket and args.project_root:
        return _serve(args.socket, args.project_root)
    parser.error("only the internal --serve mode is directly executable")


if __name__ == "__main__":
    raise SystemExit(main())
