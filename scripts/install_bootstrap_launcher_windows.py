#!/usr/bin/env python3
"""Install the verified codex-bootstrap function into a PowerShell profile."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
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
CANONICAL_REF = "main"
VERIFIED_FALLBACK_RESOLVER_SHA256 = (
    "b2a307b5d8c29604e652941e63df0bda77ae16e17cc6d5332e7ea03f7cd4ad84"
)

# Derived from the exact bounded launcher bytes read from the qualified Windows
# profile. The bytes are intentionally not copied into this repository.
HISTORICAL_LAUNCHER_SHA256 = (
    "f5f07feeefdb6074639572fcf764e89d23c6e2218a52f3d10f00fade2ca4f65d"
)

INSTALLED_LAUNCHER = b"""function codex-bootstrap {
  $staging = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-bootstrap-" + [guid]::NewGuid().ToString("N"))
  try {
    New-Item -ItemType Directory -Path $staging -Force -ErrorAction Stop | Out-Null
    $canonicalRepository = "https://github.com/matrakalaka/codex-project-bootstrap.git"
    $canonicalRef = "main"
    $fallbackResolverSha256 = "b2a307b5d8c29604e652941e63df0bda77ae16e17cc6d5332e7ea03f7cd4ad84"
    $cache = $env:CODEX_BOOTSTRAP_CACHE
    $resolverOverride = $env:CODEX_BOOTSTRAP_RESOLVER
    $canonicalCheckout = Join-Path $staging "canonical"
    $resolver = $null

    & git clone --depth 1 --no-tags --branch $canonicalRef $canonicalRepository $canonicalCheckout *> $null
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath (Join-Path $canonicalCheckout "scripts/bootstrap_authority.py") -PathType Leaf)) {
      $resolver = Join-Path $canonicalCheckout "scripts/bootstrap_authority.py"
    } elseif ($resolverOverride -and (Test-Path -LiteralPath $resolverOverride -PathType Leaf)) {
      $resolver = $resolverOverride
    } elseif ($cache -and (Test-Path -LiteralPath (Join-Path $cache "scripts/bootstrap_authority.py") -PathType Leaf)) {
      $resolver = Join-Path $cache "scripts/bootstrap_authority.py"
    } else {
      throw "BLOCKED_PRECONDITION: canonical resolver unavailable or divergent; STOP."
    }

    if ($resolver -ne (Join-Path $canonicalCheckout "scripts/bootstrap_authority.py")) {
      $resolverHash = (Get-FileHash -LiteralPath $resolver -Algorithm SHA256).Hash.ToLowerInvariant()
      if ($resolverHash -ne $fallbackResolverSha256) {
        throw "BLOCKED_PRECONDITION: resolver is not a verified historical fallback; STOP."
      }
    }

    $authorityDir = Join-Path $staging "authority"
    New-Item -ItemType Directory -Path $authorityDir -Force -ErrorAction Stop | Out-Null
    if ($resolver -eq (Join-Path $canonicalCheckout "scripts/bootstrap_authority.py")) {
      $authorityJson = & python $resolver --source-dir $canonicalCheckout --output-dir $authorityDir
    } elseif ($cache) {
      $authorityJson = & python $resolver --cache $cache --output-dir $authorityDir
    } else {
      $authorityJson = & python $resolver --output-dir $authorityDir
    }
    $resolverStatus = $LASTEXITCODE
    if ($resolverStatus -ne 0) {
      $authorityJson | Write-Error
      throw "BLOCKED_PRECONDITION: bootstrap authority unresolved; STOP."
    }

    $prompt = @"
Initialize this target project using the canonical bootstrap repository:

https://github.com/matrakalaka/codex-project-bootstrap

Authority was resolved and verified before launch:
$($authorityJson -join [Environment]::NewLine)

Read the verified GLOBAL_PROJECT_BOOTSTRAP.md and PROJECT_NORTH_STAR.md from:
$authorityDir

Perform READ-ONLY discovery only, preserve existing project authority, return the PROJECT BOOTSTRAP ASSESSMENT, and stop at the human-approval gate. Do not modify the target project before approval.
"@
    & codex --sandbox read-only $prompt
    return $LASTEXITCODE
  } catch {
    Write-Error $_
    return 2
  } finally {
    if ($staging -and (Test-Path -LiteralPath $staging)) {
      Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}
"""
INSTALLED_LAUNCHER = INSTALLED_LAUNCHER.rstrip(b"\r\n")


class InstallerBlocked(RuntimeError):
    """Raised when profile or repository safety cannot be established."""


_FUNCTION_RE = re.compile(
    rb"(?im)^[ \t]*function[ \t]+codex-bootstrap[ \t]*(?:\(\))?[ \t]*\{"
)


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
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise InstallerBlocked(f"repository HEAD is not an immutable commit: {head}")
    resolver = root / "scripts" / "bootstrap_authority.py"
    if not resolver.is_file():
        raise InstallerBlocked(f"qualified resolver is missing: {resolver}")
    try:
        _run_git(root, "cat-file", "-e", f"{head}:scripts/bootstrap_authority.py")
    except (OSError, subprocess.CalledProcessError) as error:
        raise InstallerBlocked("qualified resolver is absent from repository HEAD") from error
    return resolver


def _function_blocks(data: bytes) -> list[bytes]:
    blocks: list[bytes] = []
    for match in _FUNCTION_RE.finditer(data):
        line_start = data.rfind(b"\n", 0, match.start()) + 1
        position = line_start
        balance = 0
        end = None
        while position < len(data):
            newline = data.find(b"\n", position)
            line_end = len(data) if newline < 0 else newline
            line = data[position:line_end]
            balance += line.count(b"{") - line.count(b"}")
            if balance == 0:
                end = line_end
                if end > position and data[end - 1 : end] == b"\r":
                    end -= 1
                break
            position = len(data) if newline < 0 else newline + 1
        if end is None:
            raise InstallerBlocked("codex-bootstrap function is not structurally closed")
        blocks.append(data[line_start:end])
    return blocks


def _newline_for(block: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in block else b"\n"


def _current_launcher(block: bytes) -> bytes:
    return INSTALLED_LAUNCHER.replace(b"\n", _newline_for(block))


def _recognized(block: bytes) -> str | None:
    normalized = block.replace(b"\r\n", b"\n")
    if normalized == INSTALLED_LAUNCHER:
        return "current"
    if hashlib.sha256(block).hexdigest() == HISTORICAL_LAUNCHER_SHA256:
        return "historical"
    return None


def _backup_path(profile: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return profile.with_name(
        f"{profile.name}.codex-bootstrap.backup.{timestamp}.{os.getpid()}"
    )


def _atomic_write(path: Path, data: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.codex-bootstrap.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def install(profile: Path, repo_root: Path) -> Path | None:
    verify_repository(repo_root)
    if not profile.is_file():
        raise InstallerBlocked(f"PowerShell profile is missing: {profile}")

    original = profile.read_bytes()
    blocks = _function_blocks(original)
    if len(blocks) > 1:
        raise InstallerBlocked("expected zero or one codex-bootstrap launcher function")

    if blocks:
        state = _recognized(blocks[0])
        if state == "current":
            return None
        if state != "historical":
            raise InstallerBlocked("codex-bootstrap launcher is unknown or modified")
        newline = _newline_for(blocks[0])
        current = _current_launcher(blocks[0])
        start = original.find(blocks[0])
        block_end = start + len(blocks[0])
        replacement = original[:start] + current + original[block_end:]
    else:
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        current = _current_launcher(original)
        separator = b"" if not original or original.endswith((b"\n", b"\r")) else newline
        start = len(original) + len(separator)
        block_end = start + len(current)
        replacement = original + separator + current

    backup = _backup_path(profile)
    if backup.exists():
        raise InstallerBlocked(f"backup path already exists: {backup}")
    shutil.copy2(profile, backup)
    if backup.read_bytes() != original:
        raise InstallerBlocked("profile backup verification failed")

    try:
        _atomic_write(profile, replacement)
        written = profile.read_bytes()
        written_blocks = _function_blocks(written)
        if len(written_blocks) != 1 or _recognized(written_blocks[0]) != "current":
            raise InstallerBlocked("profile post-check failed")
        new_end = start + len(current)
        if blocks and (written[:start] != original[:start] or written[new_end:] != original[block_end:]):
            raise InstallerBlocked("profile prefix preservation failed")
        if not blocks and written[: len(original)] != original:
            raise InstallerBlocked("profile content preservation failed")
    except Exception:
        try:
            _atomic_write(profile, original)
        except Exception as restore_error:
            raise InstallerBlocked(f"profile write failed and restore failed: {restore_error}")
        raise
    return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True, help="explicit PowerShell profile path")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        backup = install(args.profile.expanduser(), args.repo_root.resolve())
    except InstallerBlocked as error:
        print(f"BLOCKED_PRECONDITION: {error}")
        return 2
    print("HOST_CHECKPOINT_OK")
    if backup is None:
        print("HOST_LAUNCHER_ALREADY_CURRENT")
    else:
        print(f"HOST_BACKUP_CREATED: {backup}")
        print("HOST_LAUNCHER_PATCH_APPLIED")
    print("HOST_POSTCHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
