"""Settings: repository root, ledger location, manifest (agentterm.toml), agent registry."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import gitinfo
from .adapters import BUILTIN, Adapter, GenericAdapter

MANIFEST_NAME = "agentterm.toml"
DEFAULT_BUDGET = 16_000


class ConfigError(ValueError):
    pass


@dataclass
class Settings:
    root: Path
    project: str
    manifest: dict[str, Any] = field(default_factory=dict)
    manifest_path: Path | None = None

    @property
    def home(self) -> Path:
        return self.root / gitinfo.INTERNAL_DIR

    @property
    def ledger_path(self) -> Path:
        return self.home / "ledger.db"

    @property
    def budget_tokens(self) -> int:
        return int(self.manifest.get("memory", {}).get("budget_tokens", DEFAULT_BUDGET))

    @property
    def default_agent(self) -> str:
        return str(self.manifest.get("project", {}).get("default_agent", "codex"))

    def adapter(self, name: str) -> Adapter | None:
        custom = self.manifest.get("agents", {}).get(name)
        if custom:
            command = custom.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
                raise ConfigError(f"agents.{name}.command must be a non-empty list of strings")
            return GenericAdapter(
                name, command, stdin=bool(custom.get("stdin", True)),
                check=custom.get("check"), interactive=custom.get("interactive"),
            )
        cls = BUILTIN.get(name)
        return cls() if cls else None

    def agent_names(self) -> list[str]:
        return sorted(set(BUILTIN) | set(self.manifest.get("agents", {})))

    def ensure_home(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        ignore = self.home / ".gitignore"
        if not ignore.exists():
            # The ledger holds prompts and responses: never commit it by accident.
            ignore.write_text("*\n", encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc


def load_settings(cwd: Path | str, manifest_path: Path | str | None = None) -> Settings:
    cwd = Path(cwd).resolve()
    snap = gitinfo.snapshot(cwd)
    root = Path(snap.root)
    path = Path(manifest_path) if manifest_path else root / MANIFEST_NAME
    manifest: dict[str, Any] = {}
    found: Path | None = None
    if path.exists():
        manifest, found = load_manifest(path), path
    elif manifest_path:
        raise ConfigError(f"manifest not found: {manifest_path}")
    return Settings(root=root, project=snap.identity, manifest=manifest, manifest_path=found)
