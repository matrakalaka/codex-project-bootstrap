import json
import sys

import pytest

from agentterm import bundle, installer, report, tui
from agentterm import gitinfo
from agentterm import ledger as L


# ------------------------------------------------------------------ installer
MANIFEST = {"tool": [
    {"id": "git", "kind": "cli", "required": True, "check": "git --version", "install": {"brew": "git"}},
    {"id": "codex", "kind": "agent", "check": "codex --version", "install": {"npm": "@openai/codex"}},
    {"id": "claude", "kind": "agent", "check": "claude --version", "install": {"npm": "@anthropic-ai/claude-code"}},
    {"id": "weird", "kind": "cli", "required": True, "check": "weird --version", "install": {"winget": "x.y"}},
    {"id": "fs", "kind": "mcp", "env": ["FS_TOKEN"], "mcp": {"command": "npx", "args": ["-y", "server-fs", "."], "env": ["FS_TOKEN"]}},
]}


def fake_which(present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def test_discovery_classification(tmp_path, monkeypatch):
    monkeypatch.delenv("FS_TOKEN", raising=False)
    statuses = {s.id: s for s in installer.discover(MANIFEST, tmp_path, platform="linux", which=fake_which({"git", "npm"}))}
    assert statuses["git"].classification == installer.ALREADY_HAVE      # real git on PATH
    assert statuses["codex"].classification == installer.OPTIONAL        # missing, planned via npm
    assert statuses["codex"].argv == ["npm", "install", "-g", "@openai/codex"]
    assert statuses["weird"].classification == installer.BLOCKED         # required, no installer on linux
    assert statuses["fs"].classification == installer.OPTIONAL and statuses["fs"].env_missing == ["FS_TOKEN"]
    plan = installer.render_plan(list(statuses.values()))
    assert "ALREADY_HAVE" in plan and "BLOCKED_PRECONDITION" in plan and "env missing: FS_TOKEN" in plan


def test_no_package_manager_means_blocked_not_guessed(tmp_path):
    s = {x.id: x for x in installer.discover(MANIFEST, tmp_path, platform="linux", which=fake_which(set()))}
    assert s["codex"].argv is None and "no usable installer" in s["codex"].detail


def test_platform_preference(tmp_path):
    manifest = {"tool": [{"id": "zz", "check": "zz --version", "install": {"brew": "zz", "npm": "zz-npm"}}]}
    both = fake_which({"brew", "npm"})
    assert installer.discover(manifest, tmp_path, platform="darwin", which=both)[0].manager == "brew"
    assert installer.discover(manifest, tmp_path, platform="linux", which=both)[0].manager == "npm"


def test_apply_runs_only_wanted_and_stops_on_failure(tmp_path):
    statuses = installer.discover(MANIFEST, tmp_path, platform="linux", which=fake_which({"npm"}))
    calls = []

    class R:
        def __init__(self, rc): self.returncode, self.stdout, self.stderr = rc, "", "denied"

    def runner(argv, **kw):
        calls.append(argv)
        return R(1 if "claude-code" in argv[-1] else 0)

    results = installer.apply(statuses, tmp_path, only=["codex", "claude"], runner=runner)
    assert [r.id for r in results] == ["codex", "claude"] and [r.ok for r in results] == [True, False]
    assert len(calls) == 2
    # Nothing optional installs without being asked.
    calls.clear()
    assert installer.apply(statuses, tmp_path, runner=runner) == [] and calls == []


def test_mcp_written_project_local_only(tmp_path):
    statuses = installer.discover(MANIFEST, tmp_path, platform="linux", which=fake_which(set()))
    fs = next(s for s in statuses if s.id == "fs")
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"existing": {"command": "x"}}}))
    results = installer.apply(statuses, tmp_path, only=["fs"])
    assert results[0].ok
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert set(data["mcpServers"]) == {"existing", "fs"}
    assert data["mcpServers"]["fs"]["env"] == {"FS_TOKEN": "${FS_TOKEN}"}   # reference, never a secret value
    again = installer.discover(MANIFEST, tmp_path, platform="linux", which=fake_which(set()))
    assert next(s for s in again if s.id == "fs").classification == installer.ALREADY_HAVE


# --------------------------------------------------------------------- bundle
def populated(tmp_path, name="a.db"):
    led = L.Ledger(tmp_path / name)
    led.append("proj", L.DECISION, {"text": "Use FTS5"})
    led.append("proj", L.FAILED, {"text": "regex parsing broke"})
    return led


def test_bundle_roundtrip_unsigned_and_signed(tmp_path):
    src = populated(tmp_path)
    key = b"team-secret"
    path = tmp_path / "b.jsonl"
    header = bundle.export_bundle(src, "proj", path, key=key)
    assert header["count"] == 2 and header["hmac"]
    dst = L.Ledger(tmp_path / "b.db")
    assert bundle.import_bundle(dst, path, project="proj", key=key) == (2, 0)
    assert bundle.import_bundle(dst, path, project="proj", key=key) == (0, 2)
    assert dst.verify().ok
    assert [e.text for e in dst.search("proj", "regex parsing")] == ["regex parsing broke"]


def test_bundle_rejections(tmp_path):
    src = populated(tmp_path)
    path = tmp_path / "b.jsonl"
    bundle.export_bundle(src, "proj", path, key=b"k1")
    dst = L.Ledger(tmp_path / "b.db")
    with pytest.raises(bundle.BundleError, match="signature"):
        bundle.import_bundle(dst, path, project="proj", key=b"wrong")
    with pytest.raises(bundle.BundleError, match="another|not this repository"):
        bundle.import_bundle(dst, path, project="other-repo", key=b"k1")
    lines = path.read_text().splitlines()
    evil = json.loads(lines[1])
    evil["text"] = "tampered"
    (tmp_path / "evil.jsonl").write_text("\n".join([lines[0], json.dumps(evil), lines[2]]) + "\n")
    with pytest.raises(bundle.BundleError, match="verification"):
        bundle.read_bundle(tmp_path / "evil.jsonl")
    (tmp_path / "short.jsonl").write_text("\n".join(lines[:2]) + "\n")
    with pytest.raises(bundle.BundleError, match="count"):
        bundle.read_bundle(tmp_path / "short.jsonl")
    assert dst.count() == 0


def test_two_teammates_share_memory_without_forking_chains(tmp_path):
    a, b = populated(tmp_path, "a.db"), L.Ledger(tmp_path / "b.db")
    b.append("proj", L.DECISION, {"text": "Teammate decision: keep adapters thin"})
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    bundle.export_bundle(a, "proj", pa)
    bundle.export_bundle(b, "proj", pb)
    bundle.import_bundle(a, pb, project="proj")
    bundle.import_bundle(b, pa, project="proj")
    assert a.count("proj") == b.count("proj") == 3
    assert a.verify().ok and b.verify().ok
    assert a.search("proj", "teammate adapters") and b.search("proj", "regex parsing")
    # each side still appends to its own chain
    mine = a.append("proj", L.NOTE, {"text": "local"})
    assert a.verify().ok and mine.prev_hash != L.GENESIS


# -------------------------------------------------------------- report and tui
def seed_sessions(led):
    led.append("proj", L.TASK, {"text": "fix <b>importer</b>", "packet": {"scope": {"allowed_paths": ["src/**"], "forbidden_paths": ["secrets/**"]}}}, session="s1", agent="codex")
    led.append("proj", L.APPROVAL, {"packet": {"approver": {"identifier": "me@example.com"}}}, session="s1", agent="codex")
    led.append("proj", L.OUTCOME, {
        "outcome": "PASS", "task": "fix <b>importer</b>", "receipt_id": "r1", "reasons": [], "changed_paths": ["src/a.py"],
        "result_packet": {"repository": {"starting_head": "a" * 40, "ending_head": "b" * 40},
                          "verification": {"result": "PASS", "checks": [{"id": "pytest", "result": "PASS", "exit_code": 0}]}}},
        session="s1", agent="codex")
    led.append("proj", L.OUTCOME, {"outcome": "DIVERGENCE", "task": "oops", "receipt_id": "r2", "reasons": ["scope violation: secrets/k"],
                                    "changed_paths": ["secrets/k"], "result_packet": {}}, session="s2", agent="claude")
    led.append("proj", L.DECISION, {"text": "Use FTS5"})
    led.append("proj", L.PARKED, {"text": "embeddings"})


def test_report_contents_and_escaping(tmp_path):
    led = L.Ledger(tmp_path / "r.db")
    seed_sessions(led)
    html = report.render_report(led, "proj", title="Evidence <script>")
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;importer" in html
    assert "ledger verified" in html and "DIVERGENCE" in html and "me@example.com" in html
    assert "Use FTS5" in html and "embeddings" in html and "secrets/k" in html
    led.db.execute("DROP TRIGGER events_no_update")
    led.db.execute("UPDATE events SET text='x' WHERE seq=1")
    assert "LEDGER FAILED VERIFICATION" in report.render_report(led, "proj")


def test_tui_view(tmp_path, repo):
    led = L.Ledger(tmp_path / "t.db")
    snap = gitinfo.snapshot(repo)
    p = snap.identity
    led.append(p, L.OBJECTIVE, {"objective": "Ship it"})
    led.append(p, L.PIN, {"text": "no prod"})
    led.append(p, L.PARKED, {"text": "later idea"})
    led.append(p, L.CONTEXT_PACK, {"budget": 1000, "used": 400, "items": [{"section": "North Star", "tokens": 100}, {"section": "Task", "tokens": 300}], "dropped": [{}]}, text="pack")
    text = tui.render_text(tui.build_view(led, p, snap, budget=1000), 80)
    assert "400/1000" in text and "Ship it" in text and "PIN" in text and "PARKED" in text and "dropped" in text
