#!/bin/zsh
emulate -L zsh
set -u

typeset repo="/Users/admin/codex-bootstrap-rc"
typeset branch="release-candidate/agentterm-bootstrap-20261018"
typeset commit="fcfd6bb80b68893b41818e7b9e29c78a39bdb48e"
typeset script_root="$(cd "$(dirname "$0")" && pwd -P)"
typeset actual_repo="$(cd "$script_root/.." && pwd -P)"
typeset stamp="$(date -u +%Y%m%dT%H%M%SZ)"
typeset root="/tmp/codex-bootstrap-host-verification-$stamp"
typeset report="$root/report.txt"
mkdir -p "$root"
touch "$report"
typeset pass=0 fail=0 skip=0 blocked=0

log() { print -r -- "$*" | tee -a "$report"; }
result() {
  typeset state="$1" name="$2" detail="$3" count="$4"
  case "$state" in
    PASS) (( pass += count )) ;;
    FAIL) (( fail += count )) ;;
    SKIP) (( skip += count )) ;;
    BLOCKED) (( blocked += count )) ;;
  esac
  log "$state: $name — $detail"
}

log "Bootstrap host verification"
log "Report: $report"
log "Artifacts: $root"
typeset missing_command=0
for required_command in python3 git grep tr; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    result FAIL "host verifier prerequisite" "required command not found: $required_command" 1
    missing_command=1
  fi
done
if [[ "$missing_command" -ne 0 ]]; then
  log "SUMMARY: PASS=$pass FAIL=$fail SKIP=$skip BLOCKED=$blocked"
  log "RESULT: NOT READY — verifier prerequisites are missing."
  exit 1
fi
if [[ "$actual_repo" == "$repo" ]]; then
  result PASS "repository identity" "$actual_repo" 1
else
  result FAIL "repository identity" "expected $repo, got $actual_repo" 1
fi
typeset got_branch="$(git -C "$actual_repo" symbolic-ref --short HEAD 2>/dev/null || true)"
typeset got_commit="$(git -C "$actual_repo" rev-parse HEAD 2>/dev/null || true)"
[[ "$got_branch" == "$branch" ]] && result PASS "branch identity" "$got_branch" 1 || result FAIL "branch identity" "expected $branch, got $got_branch" 1
if [[ "$got_commit" == "$commit" ]] || git -C "$actual_repo" merge-base --is-ancestor "$commit" "$got_commit"; then
  result PASS "candidate identity" "$got_commit (fixed candidate descends from $commit)" 1
else
  result FAIL "candidate identity" "expected $commit or its descendant, got $got_commit" 1
fi

typeset probe="$root/af_unix.txt"
python3 - "$root/socket" >"$probe" 2>&1 <<'PY'
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(sys.argv[1])
    s.close()
    print("AF_UNIX_BIND=PASS")
except Exception as exc:
    print("AF_UNIX_BIND=FAIL", type(exc).__name__, str(exc))
    raise SystemExit(1)
PY
typeset probe_rc=$?
if [[ "$probe_rc" -eq 0 ]]; then
  result PASS "AF_UNIX isolated bind" "$(tr '\n' ' ' < "$probe")" 1
else
  result BLOCKED "AF_UNIX isolated bind" "$(tr '\n' ' ' < "$probe")" 1
fi

typeset managed="$root/managed_pty.txt"
(
  cd "$repo" || exit 1
  export PYTHONPATH="$repo/scripts"
  export CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR="$root/sockets"
  mkdir -p "$CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR"
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
    test_open_terminal_bridge.OpenTerminalBridgeTests.test_managed_session_is_selected_multiline_and_audited \
    test_open_terminal_bridge.OpenTerminalBridgeTests.test_direct_socket_without_capability_is_rejected \
    test_open_terminal_bridge.OpenTerminalBridgeTests.test_timeout_terminates_session_and_queued_input_cannot_run \
    test_open_terminal_bridge.OpenTerminalBridgeTests.test_tampered_metadata_is_rejected
) >"$managed" 2>&1
typeset managed_rc=$?
if [[ "$managed_rc" -ne 0 ]]; then
  result FAIL "managed-PTY integration tests" "exit $managed_rc; see $managed" 4
elif grep -q "skipped" "$managed"; then
  result SKIP "managed-PTY integration tests" "four tests skipped; see $managed" 4
else
  result PASS "managed-PTY integration tests" "four tests executed; see $managed" 4
fi

typeset suite="$root/bootstrap_suite.txt"
(
  cd "$repo" || exit 1
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'
) >"$suite" 2>&1
typeset suite_rc=$?
typeset summary="$(python3 - "$suite" <<'PY'
import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"Ran (\d+) tests?.*?(?:OK|FAILED)(?: \(skipped=(\d+)\))?", t, re.S)
if not m:
    print("INVALID")
else:
    total = int(m.group(1))
    skipped = int(m.group(2) or 0)
    failed = len(re.findall(r"^(?:FAIL|ERROR):", t, re.M))
    print(total, skipped, failed, total - skipped - failed)
PY
)"
if [[ "$suite_rc" -ne 0 || "$summary" == "INVALID" ]]; then
  result FAIL "Bootstrap/security regression suite" "exit $suite_rc; see $suite" 1
else
  typeset total skipped failed passed
  read -r total skipped failed passed <<< "$summary"
  if [[ "$failed" -gt 0 ]]; then
    result FAIL "Bootstrap/security regression suite" "$passed passed, $failed failed, $skipped skipped of $total; see $suite" 1
  else
    result PASS "Bootstrap/security regression suite" "$passed passed of $total" 1
    [[ "$skipped" -gt 0 ]] && result SKIP "Bootstrap/security skipped cases" "$skipped skipped of $total; see $suite" "$skipped"
  fi
fi

typeset agentterm="/Users/admin/codex-bootstrap-four-tool/.bootstrap-tools/install/agentterm-venv/bin/pytest"
typeset agentlog="$root/agentterm_suite.txt"
if [[ ! -x "$agentterm" ]]; then
  result BLOCKED "vendored AgentTerm pytest suite" "not found at $agentterm" 1
else
  ( cd "$repo" && "$agentterm" -q vendor/agentterm/tests ) >"$agentlog" 2>&1
  typeset agent_rc=$?
  [[ "$agent_rc" -eq 0 ]] && result PASS "vendored AgentTerm pytest suite" "see $agentlog" 1 || result FAIL "vendored AgentTerm pytest suite" "exit $agent_rc; see $agentlog" 1
fi

typeset agentterm_exec="/Users/admin/codex-bootstrap-four-tool/.bootstrap-tools/install/agentterm-venv/bin/agentterm"
if [[ "$probe_rc" -ne 0 ]]; then
  result BLOCKED "managed Codex CLI smoke" "AF_UNIX host bind unavailable; exact rerun is: cd $repo && ./scripts/verify_bootstrap_host.sh" 1
elif [[ ! -x "$agentterm_exec" ]] || ! command -v codex >/dev/null 2>&1; then
  result BLOCKED "managed Codex CLI smoke" "AgentTerm or codex executable unavailable" 1
else
  typeset smoke="$root/smoke-project"
  typeset authority="$root/authority.json"
  typeset init_json="$root/session_init.json"
  typeset open_json="$root/session_open.json"
  typeset submit_json="$root/session_submit.json"
  typeset close_json="$root/session_close.json"
  mkdir -p "$smoke"
  (
    cd "$smoke" || exit 1
    git init -q
    git config user.email verify@example.invalid
    git config user.name "Bootstrap Host Verification"
    print -r -- "# harmless smoke project" > README.md
    git add README.md
    git commit -qm init
  )
  typeset smoke_rc=0
  (
    cd "$repo" || exit 1
    python3 scripts/bootstrap_authority.py --source-dir "$repo" --output-dir "$root/authority-files" >"$authority"
    python3 scripts/bootstrap_session.py --bootstrap-root "$repo" --project-root "$smoke" \
      --agentterm "$agentterm_exec" init --authority-json "$authority" >"$init_json"
    python3 scripts/bootstrap_session.py --bootstrap-root "$repo" --project-root "$smoke" \
      --agentterm "$agentterm_exec" terminal-open --mode managed --approve >"$open_json"
  ) || smoke_rc=$?
  if [[ "$smoke_rc" -eq 0 ]]; then
    typeset sid="$(python3 - "$open_json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("session_id", ""))
PY
)"
    if [[ -z "$sid" ]]; then
      smoke_rc=1
    else
      (
        cd "$repo" || exit 1
        python3 scripts/bootstrap_session.py --bootstrap-root "$repo" --project-root "$smoke" \
          --agentterm "$agentterm_exec" terminal-submit "$sid" --text "codex --version" \
          --approve >"$submit_json"
        python3 scripts/bootstrap_session.py --bootstrap-root "$repo" --project-root "$smoke" \
          --agentterm "$agentterm_exec" terminal-close "$sid" --approve >"$close_json"
      ) || smoke_rc=$?
    fi
  fi
  if [[ "$smoke_rc" -eq 0 ]]; then
    python3 - "$submit_json" "$close_json" "$smoke" "$sid" <<'PY'
import json, os, sys
submit = json.load(open(sys.argv[1], encoding="utf-8"))
close = json.load(open(sys.argv[2], encoding="utf-8"))
project = os.path.realpath(sys.argv[3])
sid = sys.argv[4]
if int(submit.get("returncode", -1)) != 0 or "codex" not in str(submit.get("output", "")).lower():
    raise SystemExit("codex output or exit status validation failed")
if submit.get("session_id") not in (None, sid):
    raise SystemExit("session identity validation failed")
if close.get("outcome") != "CLOSED":
    raise SystemExit("close state is not CLOSED")
if not os.path.exists(os.path.join(project, ".agentterm", "ledger.db")):
    raise SystemExit("ledger evidence missing")
if not os.path.exists(os.path.join(project, ".agentterm", "terminal-audit.jsonl")):
    raise SystemExit("terminal audit evidence missing")
print("output, exit status, session identity, close state, and audit evidence validated")
PY
    smoke_rc=$?
  fi
  if [[ "$smoke_rc" -eq 0 ]]; then
    result PASS "managed Codex CLI smoke" "codex --version and ledger/audit evidence validated" 1
  else
    result FAIL "managed Codex CLI smoke" "exit $smoke_rc; diagnostics in $root" 1
  fi
fi

log "SUMMARY: PASS=$pass FAIL=$fail SKIP=$skip BLOCKED=$blocked"
if [[ "$fail" -ne 0 || "$skip" -ne 0 || "$blocked" -ne 0 ]]; then
  log "RESULT: NOT READY — required host verification failed or remains blocked."
  log "Run from a normal owner-authorized macOS Terminal: cd $repo && ./scripts/verify_bootstrap_host.sh"
  exit 1
fi
log "RESULT: READY FOR INDEPENDENT REVIEW"
exit 0
