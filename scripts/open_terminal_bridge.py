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
import hashlib
import hmac
import json
import os
import pty
import re
import secrets
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import termios
import time
import uuid
from pathlib import Path
from typing import Any


class TerminalBridgeError(RuntimeError):
    pass


SESSION_SCHEMA = "bootstrap_terminal_session.v1"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
_PROCESS_HANDLES: dict[str, subprocess.Popen[bytes]] = {}
_MAX_OUTPUT = 1_000_000
_CAPABILITY_TTL = 24 * 60 * 60


def _session_dir(project_root: Path) -> Path:
    return project_root / ".agentterm" / "terminal-sessions"


def _metadata_path(project_root: Path, session_id: str) -> Path:
    if not _ID_RE.fullmatch(session_id):
        raise TerminalBridgeError("invalid terminal session id")
    return _session_dir(project_root) / f"{session_id}.json"


def _socket_path(project_root: Path, session_id: str) -> Path:
    # AF_UNIX addresses on macOS have a short absolute-path limit. Use a
    # private per-session directory below a validated runtime root so the
    # project path never contributes to the socket address.
    configured = os.environ.get("CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR")
    default_root = Path(tempfile.gettempdir()) / "codex-bootstrap-terminal"
    root = Path(configured).expanduser() if configured else default_root
    if len(os.fsencode(str(root))) + 24 >= 100:
        root = default_root
    _ensure_private_directory(root)
    runtime = Path(tempfile.mkdtemp(prefix="s-", dir=str(root)))
    _ensure_private_directory(runtime)
    socket_path = runtime / "session.sock"
    if len(os.fsencode(str(socket_path))) >= 104:
        _cleanup_runtime_directory(socket_path)
        raise TerminalBridgeError(
            f"terminal socket runtime path too long: {len(os.fsencode(str(socket_path)))} bytes"
        )
    return socket_path


def _ensure_private_directory(path: Path) -> None:
    """Create and validate an owner-only, non-symlink runtime directory."""
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
    except OSError as exc:
        raise TerminalBridgeError(f"terminal runtime directory unavailable: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise TerminalBridgeError("terminal runtime directory is not a real directory")
    if info.st_uid != os.getuid() or (info.st_mode & 0o077):
        raise TerminalBridgeError("terminal runtime directory ownership or permissions are unsafe")


def _validate_socket_path(path: Path, *, require_socket: bool) -> None:
    if not path.is_absolute():
        raise TerminalBridgeError("terminal socket path must be absolute")
    path_length = len(os.fsencode(str(path)))
    if path_length >= 104:
        raise TerminalBridgeError(f"terminal socket path too long: {path_length} bytes")
    _ensure_private_directory(path.parent)
    try:
        info = path.lstat()
    except FileNotFoundError:
        if require_socket:
            raise TerminalBridgeError("terminal socket is missing")
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISSOCK(info.st_mode):
        raise TerminalBridgeError("terminal socket path was substituted")
    if info.st_uid != os.getuid() or (info.st_mode & 0o077):
        raise TerminalBridgeError("terminal socket ownership or permissions are unsafe")


def _cleanup_runtime_directory(socket_path: Path) -> None:
    """Remove only an owner-only session directory and its socket."""
    runtime = socket_path.parent
    try:
        info = runtime.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            return
        if info.st_uid != os.getuid() or (info.st_mode & 0o077):
            return
        if socket_path.exists():
            socket_info = socket_path.lstat()
            if stat.S_ISLNK(socket_info.st_mode) or not stat.S_ISSOCK(socket_info.st_mode):
                return
            socket_path.unlink()
        runtime.rmdir()
    except (FileNotFoundError, OSError):
        return


def _close_process_pipes(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _reap_process_handle(session_id: str) -> None:
    process = _PROCESS_HANDLES.pop(session_id, None)
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        else:
            process.wait(timeout=0)
    finally:
        _close_process_pipes(process)


def _startup_diagnostics(process: subprocess.Popen[bytes], socket_path: Path) -> str:
    """Return bounded server-startup diagnostics without exposing secrets."""
    try:
        stderr = process.stderr
        if stderr is None:
            return f"socket_path_bytes={len(os.fsencode(str(socket_path)))}; server exit status {process.returncode}"
        data = stderr.read(4096)
    except (OSError, ValueError):
        data = b""
    detail = data.decode(errors="replace").strip()
    if len(detail) > 2000:
        detail = detail[-2000:]
    if detail:
        return f"socket_path_bytes={len(os.fsencode(str(socket_path)))}; server exit status {process.returncode}; stderr: {detail}"
    return f"socket_path_bytes={len(os.fsencode(str(socket_path)))}; server exit status {process.returncode}"


def _write_metadata(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(body, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _canonical_body(body: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in body.items() if key != "integrity"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()


def _metadata_mac(body: dict[str, Any], secret: bytes) -> str:
    return hmac.new(secret, _canonical_body(body), hashlib.sha256).hexdigest()


def _read_secret(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            raise TerminalBridgeError("terminal capability file permissions are too broad")
        raw = json.loads(path.read_text(encoding="utf-8"))
        secret = bytes.fromhex(raw["secret"])
        if len(secret) < 32 or raw.get("schema") != SESSION_SCHEMA:
            raise ValueError("invalid capability record")
        return secret, raw
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise TerminalBridgeError(f"terminal capability unavailable: {exc}") from exc


def _write_secret(path: Path, *, project_root: Path, session_id: str) -> bytes:
    secret = secrets.token_bytes(32)
    body = {"schema": SESSION_SCHEMA, "project_root": str(project_root.resolve()),
            "session_id": session_id, "created_at": time.time(),
            "expires_at": time.time() + _CAPABILITY_TTL, "secret": secret.hex()}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(body, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    return secret


def _load_metadata(project_root: Path, session_id: str) -> dict[str, Any]:
    path = _metadata_path(project_root, session_id)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise TerminalBridgeError(f"terminal session metadata unavailable: {exc}") from exc
    if not isinstance(body, dict):
        raise TerminalBridgeError("terminal session metadata must be an object")
    if body.get("schema") != SESSION_SCHEMA or body.get("project_root") != str(project_root.resolve()):
        raise TerminalBridgeError("terminal session is not bound to this project")
    capability_file = Path(body.get("capability_file", ""))
    secret, capability = _read_secret(capability_file)
    if capability.get("project_root") != str(project_root.resolve()) or capability.get("session_id") != session_id:
        raise TerminalBridgeError("terminal capability is not bound to this session and project")
    if float(capability.get("expires_at", 0)) < time.time():
        raise TerminalBridgeError("terminal capability has expired")
    if not hmac.compare_digest(str(body.get("integrity", "")), _metadata_mac(body, secret)):
        raise TerminalBridgeError("terminal session metadata integrity check failed")
    socket_path = Path(body.get("socket", ""))
    if body.get("mode") == "managed":
        if body.get("runtime_dir") != str(socket_path.parent):
            raise TerminalBridgeError("terminal runtime directory binding is inconsistent")
        _validate_socket_path(socket_path, require_socket=False)
    body["_secret"] = secret
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
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    capability_file = directory / f".{session_id}.capability"
    secret = _write_secret(capability_file, project_root=root, session_id=session_id)
    metadata = {
        "schema": SESSION_SCHEMA, "session_id": session_id,
        "project_root": str(root), "mode": mode, "state": "STARTING",
        "created_at": time.time(), "output_capture": mode == "managed",
        "capability_file": str(capability_file),
    }
    metadata_path = _metadata_path(root, session_id)
    if mode == "native":
        try:
            metadata["native_window_id"] = _native_osascript(command)
        except BaseException:
            capability_file.unlink(missing_ok=True)
            raise
        metadata["state"] = "OPEN"
        metadata["limitation"] = "new-tab launch only; arbitrary existing-tab input and output capture unsupported"
        metadata["integrity"] = _metadata_mac(metadata, secret)
        _write_metadata(metadata_path, metadata)
        return metadata

    sock = _socket_path(root, session_id)
    metadata["socket"] = str(sock)
    metadata["runtime_dir"] = str(sock.parent)
    metadata["integrity"] = _metadata_mac(metadata, secret)
    try:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve", "--socket", str(sock), "--project-root", str(root),
             "--capability-file", str(capability_file)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except BaseException:
        capability_file.unlink(missing_ok=True)
        _cleanup_runtime_directory(sock)
        raise
    _PROCESS_HANDLES[session_id] = process
    metadata["pid"] = process.pid
    metadata["integrity"] = _metadata_mac(metadata, secret)
    try:
        _write_metadata(metadata_path, metadata)
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        _PROCESS_HANDLES.pop(session_id, None)
        capability_file.unlink(missing_ok=True)
        _close_process_pipes(process)
        _cleanup_runtime_directory(sock)
        raise
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if sock.exists():
            try:
                with _connect(sock) as client:
                    _request(client, {"type": "ping"}, secret=secret, project_root=root)
                metadata["state"] = "OPEN"
                metadata["integrity"] = _metadata_mac(metadata, secret)
                _write_metadata(metadata_path, metadata)
                return metadata
            except (OSError, TerminalBridgeError):
                pass
        time.sleep(0.02)
    metadata["state"] = "FAILED"
    _write_metadata(metadata_path, metadata)
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    _PROCESS_HANDLES.pop(session_id, None)
    capability_file.unlink(missing_ok=True)
    diagnostics = _startup_diagnostics(process, sock)
    _close_process_pipes(process)
    _cleanup_runtime_directory(sock)
    raise TerminalBridgeError(f"managed terminal session did not become ready: {diagnostics}")


def _connect(sock: Path) -> socket.socket:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    try:
        client.connect(str(sock))
    except BaseException:
        client.close()
        raise
    return client


def _request(client: socket.socket, body: dict[str, Any], *, secret: bytes, project_root: Path) -> dict[str, Any]:
    request_id = uuid.uuid4().hex
    operation = str(body.get("type", ""))
    message = f"{operation}|{request_id}|{project_root.resolve()}".encode()
    authenticated = {**body, "request_id": request_id,
                     "authorization": hmac.new(secret, message, hashlib.sha256).hexdigest()}
    client.sendall((json.dumps(authenticated, sort_keys=True) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = client.recv(65536)
        if not chunk:
            raise TerminalBridgeError("terminal session disconnected")
        data += chunk
    result = json.loads(data.decode())
    if result.get("outcome") in {"BLOCKED_PRECONDITION", "UNAUTHORIZED"}:
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
            result = _request(client, {"type": "submit", "text": text, "timeout": min(max(timeout, 0.1), 30)},
                              secret=metadata["_secret"], project_root=project_root)
        if result.get("outcome") in {"TIMED_OUT_TERMINATED", "OUTPUT_LIMIT_TERMINATED"}:
            _reap_process_handle(session_id)
            metadata.pop("_secret", None)
            metadata.update(state="CLOSED", closed_at=time.time(), termination="timeout_terminated")
            metadata["integrity"] = _metadata_mac(metadata, _read_secret(Path(metadata["capability_file"]))[0])
            _write_metadata(_metadata_path(project_root.resolve(), session_id), metadata)
        elif result.get("outcome") in {"TERMINATION_FAILED", "UNKNOWN"}:
            metadata.pop("_secret", None)
            metadata.update(state="UNKNOWN", termination=result.get("outcome"))
            metadata["integrity"] = _metadata_mac(metadata, _read_secret(Path(metadata["capability_file"]))[0])
            _write_metadata(_metadata_path(project_root.resolve(), session_id), metadata)
        return result
    except OSError as exc:
        raise TerminalBridgeError(f"managed terminal session unavailable: {exc}") from exc


def close_session(project_root: Path, session_id: str, *, approved: bool) -> dict[str, Any]:
    if not approved:
        raise TerminalBridgeError("explicit owner approval is required before closing a terminal session")
    metadata = _load_metadata(project_root.resolve(), session_id)
    if metadata.get("mode") == "managed":
        try:
            with _connect(Path(metadata["socket"])) as client:
                result = _request(client, {"type": "close"}, secret=metadata["_secret"], project_root=project_root)
        except OSError as exc:
            result = {"outcome": "CLOSE_FAILED", "reason": str(exc)}
    else:
        return {"outcome": "BLOCKED_PRECONDITION", "reason": "native Terminal.app window close is not supported by this bridge", "session_id": session_id}
    metadata.pop("_secret", None)
    if result.get("outcome") == "CLOSED":
        metadata["state"] = "CLOSED"
        metadata["closed_at"] = time.time()
    elif result.get("outcome") == "CLOSE_FAILED":
        metadata["state"] = "CLOSE_FAILED"
    else:
        metadata["state"] = "UNKNOWN"
    secret, _ = _read_secret(Path(metadata["capability_file"]))
    metadata["integrity"] = _metadata_mac(metadata, secret)
    _write_metadata(_metadata_path(project_root.resolve(), session_id), metadata)
    _reap_process_handle(session_id)
    _cleanup_runtime_directory(Path(metadata.get("socket", "")))
    return {**result, "session_id": session_id}


def _audit_auth(project_root: Path, operation: str, request_id: str | None, outcome: str, reason: str = "") -> None:
    path = project_root / ".agentterm" / "terminal-audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    record = {"timestamp": time.time(), "operation": operation, "request_id": request_id,
              "outcome": outcome}
    if reason:
        record["reason"] = reason
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _authorize_request(request: dict[str, Any], *, secret: bytes, project_root: Path,
                       seen: set[str], capability: dict[str, Any]) -> tuple[bool, str]:
    operation = str(request.get("type", ""))
    request_id = request.get("request_id")
    authorization = request.get("authorization")
    if operation not in {"ping", "submit", "close"} or not isinstance(request_id, str) or not isinstance(authorization, str):
        _audit_auth(project_root, operation, request_id if isinstance(request_id, str) else None,
                    "UNAUTHORIZED", "missing or invalid authorization fields")
        return False, "missing or invalid authorization fields"
    if request_id in seen:
        _audit_auth(project_root, operation, request_id, "UNAUTHORIZED", "replayed request")
        return False, "replayed request"
    seen.add(request_id)
    if float(capability.get("expires_at", 0)) < time.time():
        _audit_auth(project_root, operation, request_id, "UNAUTHORIZED", "expired capability")
        return False, "expired capability"
    message = f"{operation}|{request_id}|{project_root.resolve()}".encode()
    expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(authorization, expected):
        _audit_auth(project_root, operation, request_id, "UNAUTHORIZED", "invalid capability")
        return False, "invalid capability"
    _audit_auth(project_root, operation, request_id, "AUTHORIZED")
    return True, ""


def _terminate_process_group(pid: int, *, grace: float = 1.0) -> str:
    try:
        pgid = os.getpgid(pid)
        if pgid in {os.getpgrp(), os.getpid()}:
            return "UNKNOWN"
        os.killpg(pgid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            os.waitpid(pid, os.WNOHANG)
            return "CLOSED"
        except OSError:
            return "UNKNOWN"
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        try:
            waited, _ = os.waitpid(pid, os.WNOHANG)
            if waited == pid:
                return "CLOSED"
        except ChildProcessError:
            return "CLOSED"
        except OSError:
            return "UNKNOWN"
        time.sleep(0.02)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    try:
        os.waitpid(pid, 0)
        return "CLOSED"
    except OSError:
        return "UNKNOWN"


def _serve(sock_path: Path, project_root: Path, capability_file: Path) -> int:
    secret, capability = _read_secret(capability_file)
    if capability.get("project_root") != str(project_root.resolve()):
        raise TerminalBridgeError("server capability is not bound to the project")
    capability_session = capability.get("session_id")
    if not isinstance(capability_session, str) or not _ID_RE.fullmatch(capability_session):
        raise TerminalBridgeError("server capability has an invalid session identity")
    _validate_socket_path(sock_path, require_socket=False)
    if sock_path.exists() or sock_path.is_symlink():
        raise TerminalBridgeError("terminal socket path collision detected")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    try:
        os.chmod(sock_path, 0o600)
    except OSError:
        pass
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
    seen_requests: set[str] = set()
    try:
        while True:
            client, _ = server.accept()
            with client:
                line = client.makefile("r", encoding="utf-8").readline()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    response = {"outcome": "UNAUTHORIZED", "reason": "invalid request encoding"}
                    client.sendall((json.dumps(response) + "\n").encode())
                    continue
                authorized, reason = _authorize_request(request, secret=secret, project_root=project_root,
                                                        seen=seen_requests, capability=capability)
                if not authorized:
                    response = {"outcome": "UNAUTHORIZED", "reason": reason}
                elif request.get("type") == "ping":
                    response = {"outcome": "PASS", "state": "OPEN"}
                elif request.get("type") == "submit":
                    response, should_close = _serve_submit(fd, request["text"], float(request.get("timeout", 10)), pid)
                    client.sendall((json.dumps(response, sort_keys=True) + "\n").encode())
                    if should_close:
                        return 0
                    continue
                elif request.get("type") == "close":
                    os.write(fd, b"exit\n")
                    termination = _terminate_process_group(pid)
                    response = {"outcome": "CLOSED" if termination == "CLOSED" else termination,
                                "termination": termination}
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
        _cleanup_runtime_directory(sock_path)


def _serve_submit(fd: int, text: str, timeout: float, shell_pid: int) -> tuple[dict[str, Any], bool]:
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
        if len(output) > _MAX_OUTPUT:
            termination = _terminate_process_group(shell_pid)
            return ({"outcome": "OUTPUT_LIMIT_TERMINATED" if termination == "CLOSED" else "TERMINATION_FAILED",
                     "reason": "terminal output exceeded the bounded capture limit",
                     "termination": termination, "output": output[-20000:].decode(errors="replace")}, True)
        if marker in output:
            break
    if marker not in output:
        termination = _terminate_process_group(shell_pid)
        if termination == "CLOSED":
            return ({"outcome": "TIMED_OUT_TERMINATED", "reason": "terminal command timed out and its session was terminated",
                     "termination": termination, "output": output.decode(errors="replace")[-20000:]}, True)
        return ({"outcome": "TERMINATION_FAILED" if termination == "UNKNOWN" else termination,
                 "reason": "terminal command timed out; session termination was not confirmed",
                 "termination": termination, "output": output.decode(errors="replace")[-20000:]}, True)
    raw = bytes(output)
    before, after = raw.rsplit(marker, 1)
    status_line = after.splitlines()[0].strip() if after.splitlines() else b"1"
    try:
        status = int(status_line)
    except ValueError:
        status = 1
    return ({"outcome": "PASS" if status == 0 else "FAILED_AFTER_EXECUTION", "returncode": status,
             "output": before.decode(errors="replace")[-20000:]}, False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--capability-file", type=Path)
    args = parser.parse_args(argv)
    if args.serve and args.socket and args.project_root and args.capability_file:
        return _serve(args.socket, args.project_root, args.capability_file)
    parser.error("only the internal --serve mode is directly executable")


if __name__ == "__main__":
    raise SystemExit(main())
