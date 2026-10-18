#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${AGENTTERM_PYTHON:-/Users/admin/ic8-stack-qualification/.venv/bin/python}
cd "$repo_dir"
export PYTHONPATH=vendor/agentterm/src

"$python_bin" -m pytest -q \
  scripts/test_open_terminal_bridge.py \
  vendor/agentterm/tests/test_platform.py \
  vendor/agentterm/tests/test_integration.py -rs

staging_root=$(mktemp -d "${TMPDIR:-/tmp}/agentterm-staging.XXXXXX")
trap 'rm -rf "$staging_root"' EXIT HUP INT TERM
"$python_bin" -m agentterm.cli staging-acceptance --root "$staging_root"
