from agentterm import brief, context, gitinfo
from agentterm import ledger as L


def seed(led, project="p"):
    led.append(project, L.OBJECTIVE, {"objective": "Ship the importer", "proof": "tests pass",
                                      "out_of_scope": "UI", "stop": "one verified checkpoint"})
    led.append(project, L.PIN, {"text": "Never touch the production database"})
    led.append(project, L.DECISION, {"text": "Use SQLite FTS5 for the importer index"})
    led.append(project, L.FAILED, {"text": "Regex-based CSV parser failed on quoted newlines"})
    led.append(project, L.NOTE, {"text": "Weekend lunch plans are unrelated pizza"})


def pack(led, task="Fix the CSV importer quoting bug", budget=2000, **kw):
    return context.build_context(led, "p", task_text=task, budget=budget, allowed=["src/**"],
                                 forbidden=["secrets/**"], mutation_allowed=True, **kw)


def test_pack_has_mandatory_sections_and_relevant_history(ledger):
    seed(ledger)
    p = pack(ledger)
    text = p.render()
    assert "Ship the importer" in text and "Never touch the production database" in text
    assert "Allowed paths: src/**" in text and "Fix the CSV importer quoting bug" in text
    assert "Regex-based CSV parser failed" in text  # relevant failure is retrieved
    assert "pizza" not in text                       # unrelated note is not
    assert not p.over_budget


def test_history_never_repeats_pins_and_respects_budget(ledger):
    seed(ledger)
    for i in range(200):
        ledger.append("p", L.NOTE, {"text": f"importer CSV quoting detail number {i} " + "x" * 200})
    p = pack(ledger, budget=900)
    assert p.used <= 900 + 150  # mandatory sections may slightly exceed, history must not
    ids = [i for it in p.items for i in it.event_ids]
    assert len(ids) == len(set(ids))
    assert any(d["reason"] == "budget exhausted" for d in p.dropped)


def test_pin_cap_drops_oldest_but_keeps_newest(ledger):
    for i in range(40):
        ledger.append("p", L.PIN, {"text": f"pinned fact {i} " + "y" * 120})
    p = pack(ledger, budget=1000)
    pinned = [it.text for it in p.items if it.section == "Pinned facts"]
    assert any("pinned fact 39" in t for t in pinned)
    assert not any("pinned fact 0 " in t for t in pinned)
    assert any(d["reason"] == "pinned-facts cap" for d in p.dropped)


def test_unset_objective_is_explicit(ledger):
    p = pack(ledger)
    assert "NOT SET" in p.render()


def test_why_explain_lists_provenance(ledger):
    seed(ledger)
    out = context.explain(pack(ledger).summary())
    assert "North Star" in out and "Pinned facts" in out and "src=" in out


def snap(**kw):
    base = dict(root="/r", is_git=True, identity="https://github.com/e/p", remote="https://github.com/e/p",
                head="a" * 40, branch="main", dirty=False, dirty_paths=())
    base.update(kw)
    return gitinfo.Snapshot(**base)


def outcome(led, kind="PASS", head="a" * 40, task="fix importer"):
    led.append("p", L.OUTCOME, {
        "outcome": kind, "task": task, "receipt_id": "r1", "reasons": [] if kind == "PASS" else ["tests failed"],
        "result_packet": {"repository": {"ending_head": head}},
        "verification": {"checks": [{"id": "pytest", "result": "PASS", "exit_code": 0}]}})


def test_checkpoint_from_events(ledger):
    seed(ledger)
    outcome(ledger)
    ledger.append("p", L.CLAIM, {"text": "I refactored the parser"})
    ledger.append("p", L.NEXT, {"text": "Add streaming support"})
    cp = brief.build_checkpoint(ledger, "p", snap())
    assert cp["status"] == "PASS" and cp["validated_head"] == "a" * 40
    assert cp["completed"] and "fix importer" in cp["completed"][0]
    assert cp["agent_claims_unverified"] == ["I refactored the parser"]
    assert cp["next_action"] == "Add streaming support"
    assert any("Regex-based CSV" in f for f in cp["failed"])
    md = brief.render_markdown(cp)
    assert brief.MARKER in md and "Verified Completed Work" in md and "UNVERIFIED" in md


def test_checkpoint_statuses(ledger):
    seed(ledger)
    outcome(ledger, "FAILED_AFTER_EXECUTION")
    cp = brief.build_checkpoint(ledger, "p", snap())
    assert cp["status"] == "FAILED" and "tests failed" in cp["failed"][0]
    assert "no automatic retry" in cp["next_action"]
    ledger.append("p", L.COMPLETE, {"text": "done"})
    assert brief.build_checkpoint(ledger, "p", snap())["next_action"] == "STOP_COMPLETE"


def test_new_objective_resets_checkpoint_view(ledger):
    seed(ledger)
    outcome(ledger)
    ledger.append("p", L.OBJECTIVE, {"objective": "Second goal"})
    cp = brief.build_checkpoint(ledger, "p", snap())
    assert cp["completed"] == [] and cp["status"] == "ACTIVE"


def test_staleness_and_isolation(ledger):
    seed(ledger)
    outcome(ledger)
    cp = brief.build_checkpoint(ledger, "p", snap())
    assert brief.validate_checkpoint(cp, snap()) == []
    moved = brief.validate_checkpoint(cp, snap(head="b" * 40, branch="feature"))
    assert {f.severity for f in moved} == {"stale"} and len(moved) == 2
    foreign = brief.validate_checkpoint(cp, snap(identity="https://github.com/other/repo"))
    assert [f.severity for f in foreign] == ["reject"]


def test_head_drift_reported_in_new_checkpoint(ledger):
    seed(ledger)
    outcome(ledger, head="a" * 40)
    cp = brief.build_checkpoint(ledger, "p", snap(head="c" * 40))
    assert any("HEAD moved" in c for c in cp["contradictions"])


def test_publish_never_overwrites_hand_written(tmp_path, ledger):
    seed(ledger)
    cp = brief.build_checkpoint(ledger, "p", snap())
    (tmp_path / "CONTINUE_TOMORROW.md").write_text("# my hand written notes\n")
    path, note = brief.write_brief(tmp_path, cp, publish=True)
    assert (tmp_path / "CONTINUE_TOMORROW.md").read_text() == "# my hand written notes\n"
    assert "preserved" in note and path.name == "CONTINUE_TOMORROW.generated.md"
    path, note = brief.write_brief(tmp_path, cp, publish=True, force=True)
    assert brief.MARKER in (tmp_path / "CONTINUE_TOMORROW.md").read_text()
    path, note = brief.write_brief(tmp_path, cp, publish=True)  # generated file may be refreshed freely
    assert note == "published CONTINUE_TOMORROW.md"
