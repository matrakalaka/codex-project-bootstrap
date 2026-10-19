#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${AGENTTERM_PYTHON:-/Users/admin/ic8-stack-qualification/.venv/bin/python}
cd "$repo_dir"
export PYTHONPATH=vendor/agentterm/src

"$python_bin" -m pytest -q \
  scripts/test_open_terminal_bridge.py \
  vendor/agentterm/tests -rs

staging_root=$(mktemp -d "${TMPDIR:-/tmp}/agentterm-staging.XXXXXX")
keychain_root=$(mktemp -d "${TMPDIR:-/tmp}/agentterm-keychain.XXXXXX")
trap 'rm -rf "$staging_root" "$keychain_root"' EXIT HUP INT TERM
"$python_bin" -m agentterm.cli staging-acceptance --root "$staging_root"

if [ "$(uname -s)" = "Darwin" ]; then
  SWIFT_MODULECACHE_PATH=$(mktemp -d "${TMPDIR:-/tmp}/agentterm-swift-cache.XXXXXX")
  trap 'rm -rf "$staging_root" "$keychain_root" "$SWIFT_MODULECACHE_PATH"' EXIT HUP INT TERM
  ./scripts/build_keychain_helper.sh "$keychain_root/AgentTermKeychain" >/dev/null
  "$python_bin" scripts/qualify_keychain_host.py --helper "$keychain_root/AgentTermKeychain"
fi
