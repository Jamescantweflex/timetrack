"""SQLite storage. One table of spans for both Mac and phone."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(
    os.environ.get(
        "TIMETRACK_DATA_DIR",
        Path.home() / "Library" / "Application Support" / "TimeTrack",
    )
)
DB_PATH = DATA_DIR / "timetrack.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    id      INTEGER PRIMARY KEY,
    source  TEXT NOT NULL,            -- 'mac' | 'phone'
    start   INTEGER NOT NULL,         -- unix seconds
    end     INTEGER NOT NULL,         -- unix seconds, >= start
    app     TEXT NOT NULL,            -- Mac app name or phone app name
    domain  TEXT,                     -- browser domain, NULL for native apps
    title   TEXT,                     -- tab/window title, may be NULL
    url     TEXT,                     -- full URL, may be NULL
    end_kind TEXT NOT NULL DEFAULT 'switch'  -- switch|idle|lock|stop|close|capped|open
);
CREATE INDEX IF NOT EXISTS spans_start ON spans(start);
CREATE INDEX IF NOT EXISTS spans_source_start ON spans(source, start);

CREATE TABLE IF NOT EXISTS phone_raw (
    line    TEXT PRIMARY KEY          -- exact JSONL line, for idempotent ingest
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn
