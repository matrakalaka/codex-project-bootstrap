#!/usr/bin/env python3
"""Install the verified codex-bootstrap function into a host zsh profile."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


CANONICAL_REPOSITORY = "https://github.com/matrakalaka/codex-project-bootstrap"
CANONICAL_GIT_URLS = {
    CANONICAL_REPOSITORY,
    CANONICAL_REPOSITORY + ".git",
    "git@github.com:matrakalaka/codex-project-bootstrap.git",
    "ssh://git@github.com/matrakalaka/codex-project-bootstrap.git",
}
EXPECTED_REVISION = "fb39ddbd5dbc4542b48c91df924c8a436cb7faa0"
EXPECTED_RESOLVER_SHA256 = "b2a307b5d8c29604e652941e63df0bda77ae16e17cc6d5332e7ea03f7cd4ad84"


EXPECTED_LAUNCHER = b'''codex-bootstrap() {
  codex --sandbox read-only 'Initialize this project using the canonical bootstrap repository:

https://github.com/matrakalaka/codex-project-bootstrap

Read GLOBAL_PROJECT_BOOTSTRAP.md first. Perform READ-ONLY discovery only, respect existing project authority, return the PROJECT BOOTSTRAP ASSESSMENT, and stop at the human-approval gate.'
}
'''


INSTALLED_LAUNCHER = b'''codex-bootstrap() {
  local canonical_revision="fb39ddbd5dbc4542b48c91df924c8a436cb7faa0"
  local resolver_sha256="b2a307b5d8c29604e652941e63df0bda77ae16e17cc6d5332e7ea03f7cd4ad84"
  local canonical_resolver_url="https://raw.githubusercontent.com/matrakalaka/codex-project-bootstrap/${canonical_revision}/scripts/bootstrap_authority.py"
  local cache="${CODEX_BOOTSTRAP_CACHE:-}"
  local resolver="${CODEX_BOOTSTRAP_RESOLVER:-}"
  local staging=""
  local authority_dir=""
  local authority_json=""
  local resolver_status=0

  staging="$(mktemp -d "${TMPDIR:-/tmp}/codex-bootstrap.XXXXXX")" || {
    printf '%s\n' "BLOCKED_PRECONDITION: could not create temporary authority workspace; STOP." >&2
    return 2
  }

  resolver="$staging/bootstrap_authority.py"
  if ! python3 - "$canonical_resolver_url" "$resolver" "$resolver_sha256" <<'PY'
import hashlib
import sys
from pathlib import Path
from urllib.request import Request, urlopen

url, destination, expected = sys.argv[1:]
request = Request(url, headers={"User-Agent": "codex-bootstrap-launcher"})
with urlopen(request, timeout=10) as response:
    content = response.read()
if hashlib.sha256(content).hexdigest() != expected:
    raise SystemExit("canonical resolver content diverged")
Path(destination).write_bytes(content)
PY
  then
    if [ -n "${CODEX_BOOTSTRAP_RESOLVER:-}" ] && [ -f "$CODEX_BOOTSTRAP_RESOLVER" ]; then
      resolver="$CODEX_BOOTSTRAP_RESOLVER"
    elif [ -n "$cache" ] && [ -f "$cache/scripts/bootstrap_authority.py" ]; then
      resolver="$cache/scripts/bootstrap_authority.py"
    else
      printf '%s\n' "BLOCKED_PRECONDITION: canonical resolver unavailable or divergent; STOP." >&2
      rm -R "$staging"
      return 2
    fi
  fi

  if ! python3 - "$resolver" "$resolver_sha256" <<'PY'
import hashlib
import sys
from pathlib import Path

path, expected = sys.argv[1:]
if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
    raise SystemExit("resolver hash mismatch")
PY
  then
    printf '%s\n' "BLOCKED_PRECONDITION: resolver is not the qualified canonical revision; STOP." >&2
    rm -R "$staging"
    return 2
  fi

  authority_dir="$staging/authority"

  if [ -n "$cache" ]; then
    authority_json="$(python3 "$resolver" --cache "$cache" --output-dir "$authority_dir")"
  else
    authority_json="$(python3 "$resolver" --output-dir "$authority_dir")"
  fi
  resolver_status=$?

  if [ "$resolver_status" -ne 0 ]; then
    printf '%s\n' "$authority_json" >&2
    printf '%s\n' "BLOCKED_PRECONDITION: bootstrap authority unresolved; STOP." >&2
    rm -R "$staging"
    return "$resolver_status"
  fi

  codex --sandbox read-only "Initialize this target project using the canonical bootstrap repository:

https://github.com/matrakalaka/codex-project-bootstrap

Authority was resolved and verified before launch:
$authority_json

Read the verified GLOBAL_PROJECT_BOOTSTRAP.md and PROJECT_NORTH_STAR.md from:
$authority_dir

Perform READ-ONLY discovery only, preserve existing project authority, return the PROJECT BOOTSTRAP ASSESSMENT, and stop at the human-approval gate. Do not modify the target project before approval."

  local codex_status=$?
  rm -R "$staging"
  return "$codex_status"
}
'''


class InstallerBlocked(RuntimeError):
    pass


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _canonical_remote(value: str) -> bool:
    return value.strip().rstrip("/") in CANONICAL_GIT_URLS


def verify_repository(root: Path) -> Path:
    try:
        origin = _run_git(root, "remote", "get-url", "origin")
        head = _run_git(root, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        raise InstallerBlocked(f"repository verification failed: {error}") from error
    if not _canonical_remote(origin):
        raise InstallerBlocked(f"repository origin is not canonical: {origin}")
    if head != EXPECTED_REVISION:
        raise InstallerBlocked(f"repository HEAD is not the expected revision: {head}")
    resolver = root / "scripts" / "bootstrap_authority.py"
    if not resolver.is_file():
        raise InstallerBlocked(f"qualified resolver is missing: {resolver}")
    actual = hashlib.sha256(resolver.read_bytes()).hexdigest()
    if actual != EXPECTED_RESOLVER_SHA256:
        raise InstallerBlocked("qualified resolver hash mismatch")
    return resolver


def install(zshrc: Path, repo_root: Path) -> Path:
    verify_repository(repo_root)
    if not zshrc.is_file():
        raise InstallerBlocked(f"launcher profile is missing: {zshrc}")
    data = zshrc.read_bytes()
    if data.count(EXPECTED_LAUNCHER) != 1:
        raise InstallerBlocked("expected codex-bootstrap function was not found exactly once")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup = zshrc.parent / f".zshrc.codex-bootstrap.backup.{timestamp}.{os.getpid()}"
    if backup.exists():
        raise InstallerBlocked(f"backup path already exists: {backup}")
    shutil.copy2(zshrc, backup)

    replacement = data.replace(EXPECTED_LAUNCHER, INSTALLED_LAUNCHER)
    mode = stat.S_IMODE(zshrc.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=".zshrc.codex-bootstrap.", dir=zshrc.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(replacement)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, zshrc)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zshrc", type=Path, default=Path.home() / ".zshrc")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        backup = install(args.zshrc.expanduser(), args.repo_root.resolve())
    except InstallerBlocked as error:
        print(f"BLOCKED_PRECONDITION: {error}", file=sys.stderr)
        return 2
    print("HOST_CHECKPOINT_OK")
    print(f"HOST_BACKUP_CREATED: {backup}")
    print("HOST_LAUNCHER_PATCH_APPLIED")
    print("HOST_POSTCHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
