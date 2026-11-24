"""Span lifecycle tests with the Mac probes mocked out. Run: python3 -m pytest -q  (or python3 tests/test_collector.py)"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from timetrack import collector as C  # noqa: E402
from timetrack import db  # noqa: E402
from timetrack.rules import Rules  # noqa: E402


class Fake:
    def __init__(self):
        self.front = C.Front("Arc", "https://x.com/home", "Home / X")
        self.idle = 0.0
        self.locked = False


def make(monkey=None):
    fake = Fake()
    C.read_front = lambda: fake.front
    C.read_idle_seconds = lambda: fake.idle
    C.screen_locked = lambda: fake.locked
    conn = db.connect(Path(":memory:")) if False else sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(db.SCHEMA)
    col = C.Collector(conn, Rules(), poll=5)
    return fake, conn, col


def spans(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM spans ORDER BY id")]


def test_heartbeat_and_switch():
    fake, conn, col = make()
    t = 1_000_000
    col.tick(t); col.tick(t + 5); col.tick(t + 10)
    s = spans(conn)
    assert len(s) == 1 and s[0]["end"] - s[0]["start"] == 10 and s[0]["domain"] == "x.com"
    fake.front = C.Front("Arc", "https://www.youtube.com/watch?v=abc", "Some video")
    col.tick(t + 15)
    s = spans(conn)
    assert len(s) == 2 and s[0]["end_kind"] == "switch" and s[0]["end"] == t + 15
    assert s[1]["domain"] == "youtube.com" and s[1]["end_kind"] == "open"


def test_idle_closes_active_but_not_passive():
    fake, conn, col = make()
    t = 1_000_000
    col.tick(t); col.tick(t + 5)
    fake.idle = 200  # over 3 min on X -> close, trimming the idle tail
    col.tick(t + 10)
    s = spans(conn)
    assert len(s) == 1 and s[0]["end_kind"] == "idle" and s[0]["end"] == s[0]["start"]  # max(start, now-idle)
    fake.idle = 0
    fake.front = C.Front("Arc", "https://youtube.com/watch?v=1", "Video")
    col.tick(t + 15); col.tick(t + 20)
    fake.idle = 1000  # 16 min no input while on YouTube: keep counting
    col.tick(t + 25)
    s = spans(conn)
    assert len(s) == 2 and s[1]["end_kind"] == "open" and s[1]["end"] == t + 25
    fake.idle = 4000  # over 60 min: stop
    col.tick(t + 30)
    assert spans(conn)[1]["end_kind"] == "idle"


def test_lock_and_sleep_gap():
    fake, conn, col = make()
    t = 1_000_000
    col.tick(t); col.tick(t + 5)
    fake.locked = True
    col.tick(t + 10)
    assert spans(conn)[0]["end_kind"] == "lock" and spans(conn)[0]["end"] == t + 10
    fake.locked = False
    col.tick(t + 15); col.tick(t + 20)
    col.tick(t + 2000)  # Mac slept: previous span ends at last heartbeat
    s = spans(conn)
    assert s[1]["end_kind"] == "stop" and s[1]["end"] == t + 20
    assert s[2]["start"] == t + 2000


def test_ignored_app_and_native_app():
    fake, conn, col = make()
    t = 1_000_000
    fake.front = C.Front("Xcode", None, "main.swift")
    col.tick(t); col.tick(t + 5)
    fake.front = C.Front("loginwindow", None, None)
    col.tick(t + 10)
    s = spans(conn)
    assert len(s) == 1 and s[0]["app"] == "Xcode" and s[0]["domain"] is None and s[0]["end_kind"] == "switch"



def test_unreadable_browser_is_flagged_once_and_in_meta():
    fake, conn, col = make()
    fake.front = C.Front("Firefox", None, "Mozilla Firefox")
    col.tick(now=1000); col.tick(now=1005); col.tick(now=1010)
    v = conn.execute("SELECT value FROM meta WHERE key='untracked_browser'").fetchone()[0]
    assert v == "Firefox|1010", v
    assert col._untracked_logged == "Firefox"
    # time is still recorded, as the bare app
    r = conn.execute("SELECT app, domain FROM spans").fetchone()
    assert r[0] == "Firefox" and r[1] is None
    fake.front = C.Front("Arc", "https://x.com/home", "X")
    col.tick(now=1015)
    assert C.installed_browsers()  # Safari at least


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
