import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from timetrack.menubar import build  # noqa: E402

NOW = 1795500000.0   # fixed clock
LIMITS = {"X": {"daily_minutes": 30, "pause_on_open": True}, "YouTube": {"daily_minutes": 45}}
SUMMARY = {"total_seconds": 7200, "categories": [
    {"category": "X", "seconds": 720, "opens": 5}, {"category": "Claude", "seconds": 3000, "opens": 9}]}


def test_title_is_watched_time_only():
    r = build(SUMMARY, LIMITS, {"enabled": True}, {}, NOW)
    assert r["title"] == "12m" and r["state"] == "ok" and r["symbol"] == "hourglass"
    assert r["lines"][0].startswith("X   12m of 30m") and "5 opens" in r["lines"][0]
    assert r["lines"][1].startswith("YouTube   0m of 45m") and "0 opens" in r["lines"][1]
    assert r["lines"][2] == "All screen time   2h 00m"


def test_over_budget():
    s = {"total_seconds": 2000, "categories": [{"category": "X", "seconds": 1900, "opens": 1}]}
    r = build(s, LIMITS, {"enabled": True}, {}, NOW)
    assert r["state"] == "over" and "(over)" in r["lines"][0] and "1 open " in r["lines"][0] + " "


def test_snoozed_and_off_and_instead():
    r = build(SUMMARY, LIMITS, {"enabled": True, "instead": "Walk"}, {"snooze_until": str(int(NOW) + 600)}, NOW)
    assert r["snoozed"] and r["state"] == "snoozed" and r["symbol"] == "moon.zzz"
    assert any(l.startswith("Snoozed until ") for l in r["lines"])
    assert "Instead: Walk" in r["lines"]
    r = build(SUMMARY, LIMITS, {"enabled": True}, {"snooze_until": str(int(NOW) - 5)}, NOW)
    assert not r["snoozed"]
    r = build(SUMMARY, LIMITS, {"enabled": False}, {}, NOW)
    assert r["state"] == "off"


def test_empty_watch_list():
    r = build({"total_seconds": 0, "categories": []}, {}, {}, {}, NOW)
    assert r["title"] == "0m" and r["lines"][0] == "Nothing on the watch list yet"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
