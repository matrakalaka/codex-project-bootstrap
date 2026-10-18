"""Native macOS Keychain bridge with a fail-closed Python boundary.

The helper uses Security.framework directly. Secret bytes cross the process
boundary only on stdin/stdout; they are never command-line arguments or logs.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
from pathlib import Path


class KeychainError(RuntimeError):
    pass


class NativeKeychainStorage:
    production_ready = False  # independent review/activation remains required

    def __init__(self, helper: Path | str, *, service: str = "com.agentterm.identity"):
        if os.sys.platform != "darwin": raise KeychainError("native macOS Keychain is unavailable on this host")
        self.helper, self.service, self._lock = Path(helper), service, threading.RLock()
        if not self.helper.is_file() or not os.access(self.helper, os.X_OK): raise KeychainError("Keychain helper is unavailable")

    def _call(self, command: str, account: str, value: bytes | None = None) -> bytes | None:
        if not account or any(ch.isspace() for ch in account): raise KeychainError("invalid Keychain account")
        request = {"command": command, "service": self.service, "account": account}
        if value is not None: request["value"] = base64.b64encode(value).decode("ascii")
        with self._lock:
            try:
                result = subprocess.run([str(self.helper)], input=json.dumps(request), text=True, capture_output=True, check=False, timeout=10)
            except (OSError, subprocess.TimeoutExpired) as exc: raise KeychainError("Keychain helper unavailable") from exc
        if result.returncode != 0:
            try: detail = json.loads(result.stderr).get("error", "Keychain operation failed")
            except json.JSONDecodeError: detail = "Keychain operation failed"
            raise KeychainError(str(detail))
        try: response = json.loads(result.stdout)
        except json.JSONDecodeError as exc: raise KeychainError("invalid Keychain helper response") from exc
        if not response.get("ok"): raise KeychainError("Keychain operation failed")
        return base64.b64decode(response["value"]) if "value" in response else None

    def put(self, key_id: str, private: bytes) -> None: self._call("put", key_id, private)
    def get(self, key_id: str) -> bytes:
        value = self._call("get", key_id)
        if value is None: raise KeychainError("Keychain item unavailable")
        return value
    def delete(self, key_id: str) -> None: self._call("delete", key_id)

