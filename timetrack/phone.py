"""Ingest iPhone open/close events written by Shortcuts into iCloud Drive.

File: iCloud Drive/Shortcuts/TimeTrack/phone_events.jsonl, one JSON object per line:
    {"ts": "2026-11-19T07:40:12+10:00", "app": "YouTube", "event": "open"}
    {"ts": "2026-11-19T07:52:03+10:00", "app": "YouTube", "event": "close"}
or the one-field form the documented shortcut writes:
    {"ts": "2026-11-19T07:40:12+10:00", "e": "YouTube open"}

Open/close pairs become spans. An open with no close is capped.
Ingest is idempotent: every raw line is remembered in phone_raw.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("timetrack.phone")

# Shortcuts can only write inside its own iCloud folder, which appears on the Mac here.
SHORTCUTS_ICLOUD = Path.home() / "Library" / "Mobile Documents" / "iCloud~is~workflow~my~workflows" / "Documents"
EVENTS_PATH = Path(os.environ.get("TIMETRACK_PHONE_FILE", SHORTCUTS_ICLOUD / "TimeTrack" / "phone_events.jsonl"))

CAP_SECONDS = 30 * 60   # an open with no close counts for at most 30 min


def parse_ts(s: str) -> int:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.astimezone()  # assume local
    return int(dt.timestamp())


def parse_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
        ts = parse_ts(str(obj["ts"]))
        if "e" in obj:                       # simple form: {"ts": ..., "e": "YouTube open"}
            app, _, event = str(obj["e"]).strip().rpartition(" ")
            app, event = app.strip(), event.lower()
        else:
            app = str(obj["app"]).strip()
            event = str(obj["event"]).strip().lower().split(" ")[0]   # "open my reason" -> "open"
    except (ValueError, KeyError, TypeError) as e:
        log.warning("bad phone line %r: %s", line[:120], e)
        return None
    if event not in ("open", "close") or not app:
        return None
    return {"ts": ts, "app": app, "event": event, "line": line}


def pair_events(events: list[dict]) -> list[dict]:
    """Turn a time-ordered list of open/close events into spans."""
    events = sorted(events, key=lambda e: e["ts"])
    open_by_app: dict[str, int] = {}
    spans: list[dict] = []

    def close(app: str, end: int, kind: str) -> None:
        start = open_by_app.pop(app)
        end = max(start, min(end, start + CAP_SECONDS))
        if end > start + CAP_SECONDS - 1 and kind == "close":
            kind = "capped"
        spans.append({"start": start, "end": end, "app": app, "end_kind": kind})

    for e in events:
        app = e["app"]
        if e["event"] == "open":
            if app in open_by_app:
                close(app, e["ts"], "capped")          # missed a close
            # Opening app B while A is open means A went to background.
            for other in list(open_by_app):
                if other != app:
                    close(other, e["ts"], "switch")
            open_by_app[app] = e["ts"]
        else:
            if app in open_by_app:
                close(app, e["ts"], "close")
            # else: close with no open, ignore
    # Still open: cap them.
    for app in list(open_by_app):
        close(app, open_by_app[app] + CAP_SECONDS, "capped")
    return spans


def ingest(conn, path: Path | None = None) -> int:
    """Read new lines, rebuild all phone spans. Returns number of new lines."""
    path = path or EVENTS_PATH
    if not path.exists():
        return 0
    seen = {r["line"] for r in conn.execute("SELECT line FROM phone_raw")}
    new = 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if not raw.strip() or raw in seen:
                continue
            conn.execute("INSERT OR IGNORE INTO phone_raw(line) VALUES(?)", (raw,))
            seen.add(raw)
            new += 1
    if new == 0:
        return 0
    rebuild(conn)
    log.info("ingested %d new phone lines", new)
    return new


def rebuild(conn) -> None:
    """Recompute every phone span from the raw lines (cheap; a few thousand lines)."""
    events = []
    for r in conn.execute("SELECT line FROM phone_raw"):
        p = parse_line(r["line"])
        if p:
            events.append(p)
    spans = pair_events(events)
    conn.execute("BEGIN")
    conn.execute("DELETE FROM spans WHERE source='phone'")
    conn.executemany(
        "INSERT INTO spans(source,start,end,app,domain,title,url,end_kind) "
        "VALUES('phone',?,?,?,NULL,NULL,NULL,?)",
        [(s["start"], s["end"], s["app"], s["end_kind"]) for s in spans],
    )
    conn.execute("COMMIT")
