"""SQLite storage.

`essays` holds exactly the agreed record schema. Supporting tables:
  essay_provenance -- evidence location, author commentary, review reasons,
                      content hash (the brief asks for these; they are kept
                      out of `essays` so its schema is unchanged)
  rejections       -- out-of-scope pages (metadata only, no essay text)
  run_events       -- per-run log of fetches, skips and errors
"""
import json
import sqlite3
from pathlib import Path

ESSAY_COLUMNS = [
    "id", "institution", "programme", "programme_category", "essay_type", "prompt_text",
    "admission_year", "essay_text", "word_count", "source_url", "source_type", "publisher",
    "acceptance_evidence", "date_scraped", "trust_level", "license_or_terms_note", "review_status",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS essays (
    id TEXT PRIMARY KEY,
    institution TEXT,
    programme TEXT,
    programme_category TEXT,
    essay_type TEXT,
    prompt_text TEXT,
    admission_year TEXT,
    essay_text TEXT NOT NULL,
    word_count INTEGER,
    source_url TEXT NOT NULL,
    source_type TEXT,
    publisher TEXT,
    acceptance_evidence TEXT,
    date_scraped TEXT,
    trust_level TEXT,
    license_or_terms_note TEXT,
    review_status TEXT NOT NULL CHECK (review_status IN ('accepted', 'needs_review'))
);
CREATE TABLE IF NOT EXISTS essay_provenance (
    id TEXT PRIMARY KEY REFERENCES essays(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    acceptance_evidence_location TEXT,
    author_commentary TEXT,
    review_reasons TEXT NOT NULL,
    content_sha256 TEXT,
    reuse_permitted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rejections (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason TEXT NOT NULL,
    institution TEXT,
    programme TEXT,
    acceptance_evidence TEXT,
    date_scraped TEXT
);
CREATE TABLE IF NOT EXISTS run_events (
    run_id TEXT NOT NULL,
    at TEXT NOT NULL,
    source_id TEXT,
    url TEXT,
    event TEXT NOT NULL,
    detail TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_essay(conn: sqlite3.Connection, record: dict, provenance: dict) -> None:
    conn.execute("DELETE FROM rejections WHERE id = ?", (record["id"],))
    cols = ", ".join(ESSAY_COLUMNS)
    marks = ", ".join("?" for _ in ESSAY_COLUMNS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in ESSAY_COLUMNS if c != "id")
    conn.execute(f"INSERT INTO essays ({cols}) VALUES ({marks}) ON CONFLICT(id) DO UPDATE SET {updates}",
                 [record[c] for c in ESSAY_COLUMNS])
    conn.execute(
        """INSERT INTO essay_provenance (id, source_id, acceptance_evidence_location, author_commentary,
               review_reasons, content_sha256, reuse_permitted) VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id,
               acceptance_evidence_location=excluded.acceptance_evidence_location,
               author_commentary=excluded.author_commentary, review_reasons=excluded.review_reasons,
               content_sha256=excluded.content_sha256, reuse_permitted=excluded.reuse_permitted""",
        (record["id"], provenance["source_id"], provenance["acceptance_evidence_location"],
         provenance["author_commentary"], json.dumps(provenance["review_reasons"]),
         provenance["content_sha256"], int(provenance["reuse_permitted"])),
    )


def record_rejection(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute("DELETE FROM essays WHERE id = ?", (row["id"],))
    conn.execute(
        """INSERT OR REPLACE INTO rejections (id, source_id, source_url, outcome, reason, institution,
               programme, acceptance_evidence, date_scraped) VALUES (?,?,?,?,?,?,?,?,?)""",
        (row["id"], row["source_id"], row["source_url"], row["outcome"], row["reason"],
         row["institution"], row["programme"], row["acceptance_evidence"], row["date_scraped"]),
    )


def log_event(conn: sqlite3.Connection, run_id: str, at: str, source_id: str | None, url: str | None,
              event: str, detail: str = "") -> None:
    conn.execute("INSERT INTO run_events VALUES (?,?,?,?,?,?)", (run_id, at, source_id, url, event, detail))


def essays_with_provenance(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT e.*, p.source_id, p.acceptance_evidence_location, p.author_commentary,
                  p.review_reasons, p.content_sha256, p.reuse_permitted
           FROM essays e JOIN essay_provenance p USING (id)
           ORDER BY e.programme_category, e.institution, e.programme, e.admission_year, e.id"""
    ).fetchall()
