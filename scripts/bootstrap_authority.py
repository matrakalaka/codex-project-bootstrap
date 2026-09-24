#!/usr/bin/env python3
"""Resolve and verify the canonical bootstrap authority without mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.request import Request, urlopen


CANONICAL_REPOSITORY = "https://github.com/matrakalaka/codex-project-bootstrap"
CANONICAL_GIT_URLS = {
    CANONICAL_REPOSITORY,
    CANONICAL_REPOSITORY + ".git",
    "git@github.com:matrakalaka/codex-project-bootstrap.git",
    "ssh://git@github.com/matrakalaka/codex-project-bootstrap.git",
}
EXPECTED_REVISION = "fb39ddbd5dbc4542b48c91df924c8a436cb7faa0"
EXPECTED_FILES = {
    "GLOBAL_PROJECT_BOOTSTRAP.md": "b9a6ed5897647ea20f17653a01cf950224bc0a3ef7b2c1cc12a9b20b7b3661fb",
    "PROJECT_NORTH_STAR.md": "bbea337fcab92e1e6bfe7531fad7a08dc6d61fc053c17018af065ad532086eaf",
}


class AuthorityBlocked(RuntimeError):
    """Raised when canonical authority cannot be established safely."""


@dataclass(frozen=True)
class Authority:
    source: str
    repository: str
    revision: str
    files: dict[str, str]
    contents: dict[str, bytes]

    def metadata(self) -> dict[str, object]:
        return {
            "source": self.source,
            "repository": self.repository,
            "revision": self.revision,
            "files": self.files,
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_git(args: Sequence[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _show_git(revision: str, name: str, cwd: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{name}"],
        cwd=cwd,
        check=True,
        capture_output=True,
    ).stdout


def _canonical_remote(value: str) -> bool:
    return value.strip().rstrip("/") in CANONICAL_GIT_URLS


def _verify_files(files: dict[str, bytes]) -> dict[str, str]:
    actual = {name: _sha256(data) for name, data in files.items()}
    if actual != EXPECTED_FILES:
        raise AuthorityBlocked(
            "canonical content divergence: "
            + json.dumps({"expected": EXPECTED_FILES, "actual": actual}, sort_keys=True)
        )
    return actual


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "codex-bootstrap-authority"})
    with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed canonical URLs
        return response.read()


def _online(fetch: Callable[[str], bytes], git: Callable[..., str]) -> Authority:
    remote = git(["ls-remote", CANONICAL_REPOSITORY + ".git", EXPECTED_REVISION])
    if not any(line.split()[0] == EXPECTED_REVISION for line in remote.splitlines() if line.split()):
        raise AuthorityBlocked("canonical revision is not advertised by the canonical Git repository")

    files = {
        name: fetch(
            f"https://raw.githubusercontent.com/matrakalaka/codex-project-bootstrap/"
            f"{EXPECTED_REVISION}/{name}"
        )
        for name in EXPECTED_FILES
    }
    return Authority(
        "canonical_git", CANONICAL_REPOSITORY, EXPECTED_REVISION,
        _verify_files(files), files,
    )


def _cached(
    cache: Path,
    git: Callable[..., str],
    show: Callable[[str, str, Path], bytes] = _show_git,
) -> Authority:
    remote = git(["remote", "get-url", "origin"], cwd=cache)
    if not _canonical_remote(remote):
        raise AuthorityBlocked("local copy remote is not the canonical bootstrap repository")

    git(["cat-file", "-e", EXPECTED_REVISION + "^{commit}"], cwd=cache)
    files: dict[str, bytes] = {}
    for name in EXPECTED_FILES:
        files[name] = show(EXPECTED_REVISION, name, cache)
    return Authority(
        "verified_cache", CANONICAL_REPOSITORY, EXPECTED_REVISION,
        _verify_files(files), files,
    )


def resolve(
    cache: Path | None = None,
    *,
    fetch: Callable[[str], bytes] = _fetch,
    git: Callable[..., str] = _run_git,
    show: Callable[[str, str, Path], bytes] = _show_git,
) -> Authority:
    """Prefer verified canonical Git content, then a verified cache.

    This function is read-only. A cache is trusted only when its origin,
    expected commit object, and required file content all match.
    """
    failures: list[str] = []
    try:
        return _online(fetch, git)
    except (AuthorityBlocked, OSError, subprocess.CalledProcessError) as error:
        failures.append(f"canonical_git: {error}")

    if cache is not None:
        try:
            return _cached(cache, git, show)
        except (AuthorityBlocked, OSError, subprocess.CalledProcessError) as error:
            failures.append(f"verified_cache: {error}")

    raise AuthorityBlocked("; ".join(failures) or "no canonical authority source was available")


def materialize(authority: Authority, output_dir: Path) -> Path:
    """Write verified authority files to a caller-owned temporary directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in authority.contents.items():
        destination = output_dir / name
        destination.write_bytes(content)
    return output_dir


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="candidate local Git cache; never modified")
    parser.add_argument("--output-dir", type=Path, help="temporary directory for verified authority files")
    args = parser.parse_args(argv)
    try:
        authority = resolve(args.cache)
        if args.output_dir:
            materialize(authority, args.output_dir)
        print(json.dumps({**authority.metadata(), "authority_dir": str(args.output_dir) if args.output_dir else None}, sort_keys=True))
        return 0
    except AuthorityBlocked as error:
        print(
            json.dumps(
                {"outcome": "BLOCKED_PRECONDITION", "reason": str(error), "stop": True},
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
