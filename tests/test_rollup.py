"""Trigger map and phone-line parsing."""
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from timetrack import db, phone, rollup  # noqa: E402
from timetrack.rules import Rules  # noqa: E402

DAY = date(2026, 11, 20)
T0 = int(datetime(2026, 11, 20, 9, 0, 0).timestamp())


def mk(spans):
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(db.SCHEMA)
    for start, end, app, domain in spans:
        conn.execute("INSERT INTO spans(source,start,end,app,domain,title,url,end_kind) VALUES('mac',?,?,?,?,?,?,?)",
                     (T0 + start, T0 + end, app, domain, "", "", "switch"))
    return conn


def test_triggers_names_what_came_before():
    conn = mk([
        (0, 300, "Slack", None),            # Slack, then straight to X
        (300, 360, "Arc", "x.com"),
        (360, 900, "Arc", "docs.google.com"),
        (900, 905, "Slack", None),          # Slack again, then X
        (905, 960, "Arc", "x.com"),
        (5000, 5060, "Arc", "x.com"),       # nothing in the minute before: came back to the Mac
        (5060, 5100, "Arc", "x.com"),       # same sitting, not a new trigger
    ])
    t = rollup.triggers(conn, Rules(), days=1, today=DAY)
    x = t["categories"]["X"]
    assert x["total"] == 3, x
    got = {f["name"]: f["count"] for f in x["from"]}
    assert got == {"Messaging": 2, "Came back to the Mac": 1}, got
    assert x["from"][0]["pct"] == 67
    assert t["categories"]["YouTube"]["total"] == 0


def test_phone_line_forms():
    a = phone.parse_line('{"ts":"2026-11-24T17:20:00+10:00","e":"YouTube open"}')
    assert a["app"] == "YouTube" and a["event"] == "open"
    b = phone.parse_line('{"ts":"2026-11-24T17:25:00+10:00","e":"YouTube Music close"}')
    assert b["app"] == "YouTube Music" and b["event"] == "close" and b["ts"] - a["ts"] == 300
    c = phone.parse_line('{"ts":"2026-11-24T07:25:00Z","app":"X","event":"open why not"}')
    assert c["app"] == "X" and c["event"] == "open"
    assert phone.parse_line('{"ts":"2026-11-24T17:20:00+10:00","e":"open"}') is None
    assert phone.parse_line("not json") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
