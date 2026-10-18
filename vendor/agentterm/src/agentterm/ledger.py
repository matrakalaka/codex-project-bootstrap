"""Append-only, hash-chained event ledger on SQLite (stdlib only).

Everything an agent session does becomes an event. Nothing is ever updated or
deleted (enforced by triggers). Memory views (pins, parked ideas, objective,
checkpoints) are derived by replaying events, so no information is lost the way
model-side compaction loses it. Each (project, origin) chain is hash-linked so
the log doubles as tamper-evident audit evidence.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .canon import canonical_hash, utc_now
from .redact import redact_obj, redact_text

GENESIS = "sha256:" + "0" * 64
MAX_TEXT = 20_000

# Event kinds. Free-form kinds are allowed; these are the ones the tool understands.
OBJECTIVE = "objective"
PIN = "pin"
UNPIN = "unpin"
PARKED = "parked"
UNPARK = "unpark"
DECISION = "decision"
FAILED = "failed_approach"
CLAIM = "claim"
NEXT = "next_action"
NOTE = "note"
TASK = "task"
ASSESSMENT = "assessment"
APPROVAL = "approval"
SESSION_START = "session_start"
SESSION_END = "session_end"
CONTEXT_PACK = "context_pack"
PROMPT = "prompt"
RESPONSE = "response"
VERIFICATION = "verification"
OUTCOME = "outcome"
CHECKPOINT = "checkpoint"
COMPLETE = "complete"
INSTALL = "install"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  ts TEXT NOT NULL,
  origin TEXT NOT NULL,
  project TEXT NOT NULL,
  session TEXT,
  agent TEXT,
  kind TEXT NOT NULL,
  body TEXT NOT NULL,
  text TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS events_project_kind ON events(project, kind, seq);
CREATE INDEX IF NOT EXISTS events_chain ON events(project, origin, seq);
CREATE INDEX IF NOT EXISTS events_session ON events(session, seq);
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(text, kind, tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS events_fts_insert AFTER INSERT ON events BEGIN
  INSERT INTO events_fts(rowid, text, kind) VALUES (new.seq, new.text, new.kind);
END;
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
  BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
"""

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has",
    "have", "had", "not", "but", "you", "your", "all", "any", "can", "will", "into",
    "its", "out", "use", "how", "what", "when", "which", "also", "then", "than",
}


@dataclass
class Event:
    seq: int
    id: str
    ts: str
    origin: str
    project: str
    session: str | None
    agent: str | None
    kind: str
    body: dict[str, Any]
    text: str
    prev_hash: str
    hash: str
    score: float = field(default=0.0, compare=False)

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id, "ts": self.ts, "origin": self.origin, "project": self.project,
            "session": self.session, "agent": self.agent, "kind": self.kind,
            "body": self.body, "text": self.text, "prev_hash": self.prev_hash,
        }

    def compute_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        data = self.payload()
        data["hash"] = self.hash
        return data

    @classmethod
    def from_row(cls, row: sqlite3.Row, score: float = 0.0) -> "Event":
        return cls(
            seq=row["seq"], id=row["id"], ts=row["ts"], origin=row["origin"],
            project=row["project"], session=row["session"], agent=row["agent"],
            kind=row["kind"], body=json.loads(row["body"]), text=row["text"],
            prev_hash=row["prev_hash"], hash=row["hash"], score=score,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            seq=0, id=data["id"], ts=data["ts"], origin=data["origin"],
            project=data["project"], session=data.get("session"), agent=data.get("agent"),
            kind=data["kind"], body=data["body"], text=data["text"],
            prev_hash=data["prev_hash"], hash=data["hash"],
        )

    @property
    def short_id(self) -> str:
        return self.id[:8]


@dataclass
class VerifyResult:
    ok: bool
    checked: int
    problems: list[str]


def fts_query(query: str, limit_terms: int = 24) -> str:
    seen: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_]{2,}", query.lower()):
        if token in _STOPWORDS or token in seen:
            continue
        seen.append(token)
        if len(seen) >= limit_terms:
            break
    return " OR ".join(f'"{t}"' for t in seen)


def _default_text(kind: str, body: dict[str, Any]) -> str:
    value = body.get("text")
    if isinstance(value, str) and value:
        return value
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


class Ledger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('ledger_id', ?)", (uuid.uuid4().hex,)
        )
        self.ledger_id: str = self.db.execute(
            "SELECT value FROM meta WHERE key='ledger_id'"
        ).fetchone()[0]

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        # Short-lived CLI helpers historically relied on GC. Close defensively
        # so Python 3.14 does not report an unclosed sqlite handle.
        try:
            db = getattr(self, "db", None)
            if db is not None:
                db.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ writes
    def append(
        self,
        project: str,
        kind: str,
        body: dict[str, Any] | None = None,
        *,
        text: str | None = None,
        session: str | None = None,
        agent: str | None = None,
        ts: str | None = None,
        redact: bool = True,
    ) -> Event:
        body = dict(body or {})
        if redact:
            body = redact_obj(body)
        text = text if text is not None else _default_text(kind, body)
        if redact:
            text = redact_text(text)
        text = text[:MAX_TEXT]
        event_id = uuid.uuid4().hex
        ts = ts or utc_now()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT hash FROM events WHERE project=? AND origin=? ORDER BY seq DESC LIMIT 1",
                (project, self.ledger_id),
            ).fetchone()
            event = Event(
                seq=0, id=event_id, ts=ts, origin=self.ledger_id, project=project,
                session=session, agent=agent, kind=kind, body=body, text=text,
                prev_hash=row[0] if row else GENESIS, hash="",
            )
            event.hash = event.compute_hash()
            cur = self._insert(event)
            event.seq = cur
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return event

    def _insert(self, event: Event) -> int:
        cur = self.db.execute(
            "INSERT INTO events(id, ts, origin, project, session, agent, kind, body, text,"
            " prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                event.id, event.ts, event.origin, event.project, event.session, event.agent,
                event.kind, json.dumps(event.body, ensure_ascii=False, sort_keys=True),
                event.text, event.prev_hash, event.hash,
            ),
        )
        return int(cur.lastrowid)

    def import_events(self, events: Iterable[dict[str, Any]]) -> tuple[int, int]:
        """Atomically import foreign events. Returns (imported, skipped_duplicates)."""
        imported = skipped = 0
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for raw in events:
                event = Event.from_dict(raw)
                if self.db.execute("SELECT 1 FROM events WHERE id=?", (event.id,)).fetchone():
                    skipped += 1
                    continue
                if event.compute_hash() != event.hash:
                    raise ValueError(f"event {event.id[:8]} fails hash verification")
                tail = self.db.execute(
                    "SELECT hash FROM events WHERE project=? AND origin=? ORDER BY seq DESC LIMIT 1",
                    (event.project, event.origin),
                ).fetchone()
                expected_prev = tail[0] if tail else GENESIS
                if event.prev_hash != expected_prev:
                    raise ValueError(f"event {event.id[:8]} does not extend its chain")
                self._insert(event)
                imported += 1
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return imported, skipped

    # ------------------------------------------------------------------- reads
    def events(
        self,
        project: str | None = None,
        *,
        kinds: Iterable[str] | None = None,
        session: str | None = None,
        after_seq: int = 0,
        limit: int | None = None,
        desc: bool = False,
    ) -> list[Event]:
        sql = "SELECT * FROM events WHERE seq > ?"
        params: list[Any] = [after_seq]
        if project is not None:
            sql += " AND project = ?"
            params.append(project)
        if session is not None:
            sql += " AND session = ?"
            params.append(session)
        if kinds:
            kinds = list(kinds)
            sql += " AND kind IN (%s)" % ",".join("?" * len(kinds))
            params.extend(kinds)
        sql += " ORDER BY seq " + ("DESC" if desc else "ASC")
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return [Event.from_row(r) for r in self.db.execute(sql, params)]

    def get(self, event_id: str) -> Event | None:
        row = self.db.execute("SELECT * FROM events WHERE id = ? OR id LIKE ?", (event_id, event_id + "%")).fetchone()
        return Event.from_row(row) if row else None

    def latest(self, project: str, kind: str) -> Event | None:
        found = self.events(project, kinds=[kind], limit=1, desc=True)
        return found[0] if found else None

    def count(self, project: str | None = None) -> int:
        if project is None:
            return int(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        return int(self.db.execute("SELECT COUNT(*) FROM events WHERE project=?", (project,)).fetchone()[0])

    def projects(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT DISTINCT project FROM events ORDER BY project")]

    def search(
        self,
        project: str,
        query: str,
        *,
        limit: int = 10,
        kinds: Iterable[str] | None = None,
        exclude_kinds: Iterable[str] | None = None,
    ) -> list[Event]:
        match = fts_query(query)
        if not match:
            return []
        sql = (
            "SELECT e.*, bm25(events_fts) AS score FROM events_fts "
            "JOIN events e ON e.seq = events_fts.rowid "
            "WHERE events_fts MATCH ? AND e.project = ?"
        )
        params: list[Any] = ["text : (" + match + ")", project]
        if kinds:
            kinds = list(kinds)
            sql += " AND e.kind IN (%s)" % ",".join("?" * len(kinds))
            params.extend(kinds)
        if exclude_kinds:
            exclude_kinds = list(exclude_kinds)
            sql += " AND e.kind NOT IN (%s)" % ",".join("?" * len(exclude_kinds))
            params.extend(exclude_kinds)
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        return [Event.from_row(r, score=float(r["score"])) for r in self.db.execute(sql, params)]

    # --------------------------------------------------------- derived memory
    def objective(self, project: str) -> Event | None:
        return self.latest(project, OBJECTIVE)

    def pins(self, project: str) -> list[Event]:
        removed = {e.body.get("pin_id") for e in self.events(project, kinds=[UNPIN])}
        return [e for e in self.events(project, kinds=[PIN]) if e.id not in removed]

    def parked(self, project: str) -> list[Event]:
        removed = {e.body.get("parked_id") for e in self.events(project, kinds=[UNPARK])}
        return [e for e in self.events(project, kinds=[PARKED]) if e.id not in removed]

    def chain_head(self, project: str) -> str:
        row = self.db.execute(
            "SELECT hash FROM events WHERE project=? AND origin=? ORDER BY seq DESC LIMIT 1",
            (project, self.ledger_id),
        ).fetchone()
        return row[0] if row else GENESIS

    # ------------------------------------------------------------ verification
    def verify(self, project: str | None = None) -> VerifyResult:
        problems: list[str] = []
        checked = 0
        sql = "SELECT DISTINCT project, origin FROM events"
        params: list[Any] = []
        if project is not None:
            sql += " WHERE project = ?"
            params.append(project)
        for chain_project, origin in [tuple(r) for r in self.db.execute(sql, params)]:
            prev = GENESIS
            rows = self.db.execute(
                "SELECT * FROM events WHERE project=? AND origin=? ORDER BY seq",
                (chain_project, origin),
            )
            for row in rows:
                event = Event.from_row(row)
                checked += 1
                if event.prev_hash != prev:
                    problems.append(f"seq {event.seq} ({event.short_id}): broken chain link")
                if event.compute_hash() != event.hash:
                    problems.append(f"seq {event.seq} ({event.short_id}): content hash mismatch")
                prev = event.hash
        return VerifyResult(not problems, checked, problems)


def verify_events(events: list[dict[str, Any]]) -> list[str]:
    """Verify an exported chain (list of event dicts for one project and origin)."""
    problems: list[str] = []
    prev = GENESIS
    for raw in events:
        event = Event.from_dict(raw)
        if event.prev_hash != prev:
            problems.append(f"{event.short_id}: broken chain link")
        if event.compute_hash() != event.hash:
            problems.append(f"{event.short_id}: content hash mismatch")
        prev = event.hash
    return problems
