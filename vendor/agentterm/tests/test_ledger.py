import sqlite3

import pytest

from agentterm import ledger as L
from agentterm.canon import canonical_hash
from agentterm.redact import redact_text


def test_append_chains_and_verifies(ledger):
    a = ledger.append("p", "note", {"text": "first"})
    b = ledger.append("p", "note", {"text": "second"})
    assert a.prev_hash == L.GENESIS
    assert b.prev_hash == a.hash
    assert ledger.verify().ok
    assert ledger.verify().checked == 2


def test_ledger_context_manager_closes_connection(tmp_path):
    with L.Ledger(tmp_path / "context.db") as led:
        led.append("project", "note", {"text": "closed"})
    with pytest.raises(sqlite3.ProgrammingError):
        led.count()


def test_chains_are_per_project(ledger):
    ledger.append("p1", "note", {"text": "a"})
    c = ledger.append("p2", "note", {"text": "b"})
    assert c.prev_hash == L.GENESIS


def test_append_only_triggers(ledger):
    ledger.append("p", "note", {"text": "x"})
    with pytest.raises(sqlite3.DatabaseError):
        ledger.db.execute("UPDATE events SET text='tampered'")
    with pytest.raises(sqlite3.DatabaseError):
        ledger.db.execute("DELETE FROM events")


def test_tamper_detection(tmp_path):
    led = L.Ledger(tmp_path / "t.db")
    led.append("p", "note", {"text": "keep"})
    led.append("p", "note", {"text": "also"})
    # An attacker with raw file access drops the triggers and edits a row.
    led.db.execute("DROP TRIGGER events_no_update")
    led.db.execute("UPDATE events SET text='edited' WHERE seq=1")
    result = led.verify()
    assert not result.ok
    assert any("hash mismatch" in p for p in result.problems)


def test_search_ranks_relevant_and_ignores_noise(ledger):
    ledger.append("p", "decision", {"text": "Use SQLite FTS5 for retrieval of memory"})
    ledger.append("p", "note", {"text": "Lunch order was pizza"})
    ledger.append("other", "decision", {"text": "SQLite is used elsewhere"})
    hits = ledger.search("p", "which retrieval should memory use? sqlite")
    assert [h.text for h in hits][0].startswith("Use SQLite")
    assert all(h.project == "p" for h in hits)
    assert ledger.search("p", "the and for") == []  # only stopwords


def test_search_handles_hostile_query(ledger):
    ledger.append("p", "note", {"text": "alpha beta"})
    assert ledger.search("p", 'alpha" OR NOT ( * ) -- ;') != [] or True  # must not raise


def test_pins_and_parked_are_derived(ledger):
    pin = ledger.append("p", L.PIN, {"text": "never touch prod"})
    ledger.append("p", L.PIN, {"text": "tests live in tests/"})
    assert len(ledger.pins("p")) == 2
    ledger.append("p", L.UNPIN, {"pin_id": pin.id})
    assert [e.text for e in ledger.pins("p")] == ["tests live in tests/"]
    idea = ledger.append("p", L.PARKED, {"text": "add embeddings"})
    assert len(ledger.parked("p")) == 1
    ledger.append("p", L.UNPARK, {"parked_id": idea.id})
    assert ledger.parked("p") == []


def test_redaction_on_write(ledger):
    secret = "sk-" + "a" * 30
    ev = ledger.append("p", "note", {"text": f"key is {secret}", "nested": {"t": secret}})
    assert secret not in ev.text
    assert secret not in str(ev.body)
    assert ledger.verify().ok


def test_redact_patterns():
    assert "ghp_" not in redact_text("token ghp_" + "b" * 36)
    assert "AKIA" not in redact_text("AKIAABCDEFGHIJKLMNOP")
    assert "hunter22hunter" not in redact_text("password = hunter22hunter")
    assert redact_text("plain text") == "plain text"


def test_import_roundtrip_and_dedupe(tmp_path):
    src = L.Ledger(tmp_path / "a.db")
    for i in range(3):
        src.append("p", "note", {"text": f"event {i}"})
    exported = [e.as_dict() for e in src.events("p")]
    dst = L.Ledger(tmp_path / "b.db")
    assert dst.import_events(exported) == (3, 0)
    assert dst.import_events(exported) == (0, 3)
    assert dst.verify().ok
    assert dst.verify().checked == 3
    # Incremental: more events upstream extend the imported chain.
    src.append("p", "note", {"text": "event 3"})
    again = [e.as_dict() for e in src.events("p")]
    assert dst.import_events(again) == (1, 3)
    assert dst.verify().ok


def test_import_rejects_tampered_and_gapped(tmp_path):
    src = L.Ledger(tmp_path / "a.db")
    for i in range(3):
        src.append("p", "note", {"text": f"event {i}"})
    exported = [e.as_dict() for e in src.events("p")]
    tampered = [dict(e) for e in exported]
    tampered[1]["text"] = "evil"
    dst = L.Ledger(tmp_path / "b.db")
    with pytest.raises(ValueError):
        dst.import_events(tampered)
    assert dst.count() == 0  # atomic
    with pytest.raises(ValueError):
        dst.import_events(exported[1:])  # chain gap


def test_canonical_hash_is_order_independent():
    assert canonical_hash({"b": 1, "a": [1, 2]}) == canonical_hash({"a": [1, 2], "b": 1})
