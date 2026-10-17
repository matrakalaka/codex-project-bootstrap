# Bootstrap Sandbox Recovery

## Root-cause model

Sandbox recovery distinguishes five layers:

1. **Codex policy** — approval mode and sandbox scope control filesystem,
   subprocess, network, and localhost behavior. Full-auto/YOLO-like modes do
   not grant macOS privacy permissions or unrestricted host access.
2. **macOS privacy/security** — Terminal automation, protected directories,
   and application control are governed by macOS privacy controls.
3. **Parent process** — a command inherits the limits of the process that
   launched Codex; opening a normal Terminal window does not retroactively
   expand the existing agent process.
4. **Managed-device policy** — enterprise controls can deny host execution or
   prevent changing privacy settings. This requires administrator action.
5. **Registration/project defects** — missing MCP entries, wrong paths, absent
   runtimes, and project-specific bugs are separate from sandbox policy.

The current Bootstrap MCP configuration is not modified by this repository.
The repository-local registration is declarative and is validated before any
host/session configuration is considered.

## Safe host bridge

`scripts/host_exec_bridge.py` is a small opt-in helper for an owner-approved
host process. It is not an unrestricted shell and it cannot defeat Codex's
sandbox. It:

- accepts only named operations (`git_status` and synthetic `fixture_echo`);
- rejects all shell strings, pipelines, redirections, and unknown operations;
- requires `CODEX_BOOTSTRAP_HOST_EXECUTION=1`;
- requires `--approve` plus `authorization: OWNER_APPROVED`;
- records the exact allowlisted argv, target, result, and output in JSONL;
- applies a ten-second timeout;
- returns `BLOCKED_PRECONDITION` when host execution is unavailable.

The bridge must be launched from an approved normal macOS Terminal or helper
when host execution is genuinely required. It does not change TCC settings,
disable SIP, open a remote shell, contact devices, or modify global Codex
configuration.

Synthetic check:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_host_exec_bridge.py' -v
```

No test invokes ADB, Android transport, port `15041`, browser automation, or
production services.

## Owner/admin boundary

If the bridge reports `BLOCKED_PRECONDITION` despite an approved request, the
next action is administrative: grant the specific macOS permission or use an
approved host runner. Do not retry with broader privileges, disable security,
or interpret YOLO/full-auto as proof of host access.
