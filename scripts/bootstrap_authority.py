#!/usr/bin/env python3
"""Resolve and verify canonical bootstrap authority without target mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


CANONICAL_REPOSITORY = "https://github.com/matrakalaka/codex-project-bootstrap"
CANONICAL_GIT_URLS = {
    CANONICAL_REPOSITORY,
    CANONICAL_REPOSITORY + ".git",
    "git@github.com:matrakalaka/codex-project-bootstrap.git",
    "ssh://git@github.com/matrakalaka/codex-project-bootstrap.git",
}
CANONICAL_REF = "main"
REQUIRED_FILES = ("GLOBAL_PROJECT_BOOTSTRAP.md", "PROJECT_NORTH_STAR.md")

# Historical offline trust anchor. Online resolution derives the current
# immutable commit from Git and does not use this as a publication pin.
VERIFIED_FALLBACK_REVISION = "fb39ddbd5dbc4542b48c91df924c8a436cb7faa0"
VERIFIED_FALLBACK_FILES = {
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
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
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


def _verify_files(
    files: dict[str, bytes], expected: dict[str, str] | None = None
) -> dict[str, str]:
    actual = {name: _sha256(data) for name, data in files.items()}
    if expected is not None and actual != expected:
        raise AuthorityBlocked(
            "canonical content divergence: "
            + json.dumps({"expected": expected, "actual": actual}, sort_keys=True)
        )
    return actual


def _authority_from_checkout(
    checkout: Path,
    git: Callable[..., str],
    show: Callable[[str, str, Path], bytes],
    source: str,
    expected_revision: str | None = None,
    expected_files: dict[str, str] | None = None,
) -> Authority:
    remote = git(["remote", "get-url", "origin"], cwd=checkout)
    if not _canonical_remote(remote):
        raise AuthorityBlocked("local copy remote is not the canonical bootstrap repository")

    revision = git(["rev-parse", "HEAD"], cwd=checkout)
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise AuthorityBlocked("canonical checkout did not resolve to an immutable commit")
    if expected_revision is not None and revision != expected_revision:
        raise AuthorityBlocked("verified fallback revision mismatch")

    files = {name: show("HEAD", name, checkout) for name in REQUIRED_FILES}
    hashes = _verify_files(files, expected_files)
    return Authority(source, CANONICAL_REPOSITORY, revision, hashes, files)


def _clone_canonical(destination: Path) -> None:
    subprocess.run(
        [
            "git", "clone", "--depth", "1", "--no-tags", "--branch", CANONICAL_REF,
            CANONICAL_REPOSITORY + ".git", str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _online(
    git: Callable[..., str],
    show: Callable[[str, str, Path], bytes],
    clone: Callable[[Path], None] = _clone_canonical,
) -> Authority:
    with tempfile.TemporaryDirectory(prefix="codex-bootstrap-canonical-") as directory:
        checkout = Path(directory) / "repository"
        clone(checkout)
        return _authority_from_checkout(checkout, git, show, "canonical_git")


def _cached(
    cache: Path,
    git: Callable[..., str],
    show: Callable[[str, str, Path], bytes] = _show_git,
) -> Authority:
    return _authority_from_checkout(
        cache, git, show, "verified_cache",
        expected_revision=VERIFIED_FALLBACK_REVISION,
        expected_files=VERIFIED_FALLBACK_FILES,
    )


def resolve(
    cache: Path | None = None,
    *,
    source_dir: Path | None = None,
    git: Callable[..., str] = _run_git,
    show: Callable[[str, str, Path], bytes] = _show_git,
    clone: Callable[[Path], None] = _clone_canonical,
) -> Authority:
    """Resolve current canonical Git authority, then a verified historical cache."""
    failures: list[str] = []
    try:
        if source_dir is not None:
            return _authority_from_checkout(source_dir, git, show, "canonical_git")
        return _online(git, show, clone)
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
        (output_dir / name).write_bytes(content)
    return output_dir


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="candidate historical verified Git cache; never modified")
    parser.add_argument("--source-dir", type=Path, help="already-cloned canonical Git snapshot; never modified")
    parser.add_argument("--output-dir", type=Path, help="temporary directory for verified authority files")
    args = parser.parse_args(argv)
    try:
        authority = resolve(args.cache, source_dir=args.source_dir)
        if args.output_dir:
            materialize(authority, args.output_dir)
        print(json.dumps({**authority.metadata(), "authority_dir": str(args.output_dir) if args.output_dir else None}, sort_keys=True))
        return 0
    except AuthorityBlocked as error:
        print(json.dumps({"outcome": "BLOCKED_PRECONDITION", "reason": str(error), "stop": True}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
