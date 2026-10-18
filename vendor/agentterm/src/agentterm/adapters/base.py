"""Agent adapters: how to launch an agent CLI and hand it a prompt."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass


@dataclass
class AgentResult:
    text: str
    returncode: int
    stderr: str
    duration: float
    timed_out: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


class Adapter:
    """Base adapter. Subclasses define ``command`` and optional doctor metadata."""

    name = ""
    binary = ""
    #: Flags the adapter relies on; ``doctor`` checks they still appear in ``--help``.
    required_flags: tuple[str, ...] = ()
    help_args: tuple[str, ...] = ("--help",)
    version_args: tuple[str, ...] = ("--version",)
    #: Whether the agent can be launched read-only by flag (otherwise scope checks are the only net).
    enforces_read_only = False

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def _probe(self, args: tuple[str, ...]) -> str | None:
        try:
            r = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return (r.stdout or "") + (r.stderr or "")

    def version(self) -> str | None:
        out = self._probe(self.version_args)
        return out.strip().splitlines()[0] if out and out.strip() else None

    def doctor(self) -> dict:
        info = {"agent": self.name, "binary": self.binary, "available": self.available(),
                "version": None, "missing_flags": [], "enforces_read_only": self.enforces_read_only}
        if not info["available"]:
            return info
        info["version"] = self.version()
        if self.required_flags:
            help_text = self._probe(self.help_args) or ""
            info["missing_flags"] = [f for f in self.required_flags if f not in help_text]
        return info

    # --- to override
    def command(self, *, mutation_allowed: bool, cwd: str, is_git: bool, prompt: str) -> tuple[list[str], str | None]:
        raise NotImplementedError

    def interactive_command(self, prompt: str) -> list[str]:
        return [self.binary, prompt]

    # --- shared
    def run(self, prompt: str, *, cwd: str, mutation_allowed: bool, is_git: bool,
            timeout: int, env: dict[str, str] | None = None) -> AgentResult:
        argv, stdin = self.command(mutation_allowed=mutation_allowed, cwd=cwd, is_git=is_git, prompt=prompt)
        start = time.monotonic()
        try:
            r = subprocess.run(argv, input=stdin, cwd=cwd, capture_output=True, text=True,
                               timeout=timeout, env={**os.environ, **(env or {})})
        except subprocess.TimeoutExpired as exc:
            return AgentResult(_decode(exc.stdout), 124, _decode(exc.stderr),
                               time.monotonic() - start, timed_out=True)
        except OSError as exc:
            return AgentResult("", 127, str(exc), time.monotonic() - start, error=str(exc))
        return AgentResult(r.stdout, r.returncode, r.stderr, time.monotonic() - start)
