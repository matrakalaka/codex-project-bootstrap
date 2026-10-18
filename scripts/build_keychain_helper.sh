#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=${1:-"$repo_dir/.build/AgentTermKeychain"}
mkdir -p "$(dirname -- "$out")"
cache=${SWIFT_MODULECACHE_PATH:-"${TMPDIR:-/tmp}/agentterm-swift-module-cache"}
mkdir -p "$cache"
swiftc -module-cache-path "$cache" -O -framework Security -o "$out" "$repo_dir/vendor/agentterm/native/AgentTermKeychain.swift"
chmod 700 "$out"
printf '%s\n' "$out"
