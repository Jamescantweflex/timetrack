"""Queries over spans: categorise, sessionise, summarise."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from .rules import Rules

SESSION_GAP = 60  # seconds between spans of one category that still count as one session


def day_bounds(d: date) -> tuple[int, int]:
    start = datetime(d.year, d.month, d.day).astimezone()
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def load_spans(conn, start: int, end: int, rules: Rules) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM spans WHERE end > ? AND start < ? ORDER BY start",
        (start, end),
    )
    out = []
    for r in rows:
        s = dict(r)
        s["start"] = max(s["start"], start)
        s["end"] = min(s["end"], end)
        s["category"] = rules.categorise(s["source"], s["app"], s["domain"])
        s["seconds"] = max(0, s["end"] - s["start"])
        out.append(s)
    return out


def sessions(spans: list[dict], gap: int = SESSION_GAP) -> list[dict]:
    """Merge consecutive spans of the same category (per source) into sessions."""
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for s in sorted(spans, key=lambda s: s["start"]):
        key = (s["source"], s["category"])
        lst = by_key[key]
        if lst and s["start"] - lst[-1]["end"] <= gap:
            lst[-1]["end"] = max(lst[-1]["end"], s["end"])
            lst[-1]["spans"] += 1
            if s.get("title") and s["title"] not in lst[-1]["titles"]:
                lst[-1]["titles"].append(s["title"])
        else:
            lst.append({
                "source": s["source"], "category": s["category"],
                "start": s["start"], "end": s["end"], "spans": 1,
                "titles": [s["title"]] if s.get("title") else [],
            })
    result = [x for lst in by_key.values() for x in lst]
    for x in result:
        x["seconds"] = x["end"] - x["start"]
    result.sort(key=lambda x: x["start"])
    return result


def summary(conn, d: date, rules: Rules) -> dict:
    start, end = day_bounds(d)
    spans = load_spans(conn, start, end, rules)
    sess = sessions(spans)
    by_cat: dict[str, dict] = defaultdict(lambda: {"seconds": 0, "opens": 0, "mac": 0, "phone": 0})
    for s in spans:
        c = by_cat[s["category"]]
        c["seconds"] += s["seconds"]
        c[s["source"]] += s["seconds"]
    for x in sess:
        by_cat[x["category"]]["opens"] += 1
    cats = [{"category": k, **v} for k, v in by_cat.items()]
    cats.sort(key=lambda c: -c["seconds"])
    tracked = {c["category"] for c in cats} | set(rules.tracked_names())
    for name in rules.tracked_names():
        if name not in {c["category"] for c in cats}:
            cats.append({"category": name, "seconds": 0, "opens": 0, "mac": 0, "phone": 0})
    total = sum(c["seconds"] for c in cats)
    return {
        "date": d.isoformat(),
        "total_seconds": total,
        "categories": cats,
        "tracked": sorted(tracked & set(rules.tracked_names())),
        "sessions": sess,
    }


def hourly(conn, d: date, rules: Rules, categories: list[str] | None = None) -> dict:
    """Seconds per hour per category for one day."""
    start, end = day_bounds(d)
    spans = load_spans(conn, start, end, rules)
    grid: dict[str, list[int]] = defaultdict(lambda: [0] * 24)
    for s in spans:
        if categories and s["category"] not in categories:
            continue
        t = s["start"]
        while t < s["end"]:
            hour_start = datetime.fromtimestamp(t).replace(minute=0, second=0, microsecond=0)
            hour_end = int((hour_start + timedelta(hours=1)).timestamp())
            chunk_end = min(hour_end, s["end"])
            grid[s["category"]][hour_start.hour] += chunk_end - t
            t = chunk_end
    return {"date": d.isoformat(), "hours": grid}


def week(conn, end_day: date, rules: Rules, days: int = 7) -> list[dict]:
    out = []
    for i in range(days - 1, -1, -1):
        d = end_day - timedelta(days=i)
        s = summary(conn, d, rules)
        out.append({
            "date": s["date"],
            "weekday": d.strftime("%a"),
            "total_seconds": s["total_seconds"],
            "categories": {c["category"]: {"seconds": c["seconds"], "opens": c["opens"]} for c in s["categories"]},
        })
    return out


def fmt_hm(seconds: int) -> str:
    m = int(round(seconds / 60))
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def triggers(conn, rules: Rules, days: int = 14, today: date | None = None, lookback: int = 60) -> dict:
    """What was in front in the minute before each sitting on a watched category.

    For every Mac session on a category that has limits, find the last span of
    a different category that ended within `lookback` seconds of the session
    start. No such span means the Mac was idle, asleep or locked just before:
    "Came back to the Mac".
    """
    today = today or date.today()
    start, _ = day_bounds(today - timedelta(days=days - 1))
    _, end = day_bounds(today)
    spans = [s for s in load_spans(conn, start, end, rules)
             if s["source"] == "mac" and s["app"] not in rules.ignore_apps]
    spans.sort(key=lambda s: s["start"])
    own = {"127.0.0.1", "localhost"}       # our own dashboard: where a "wasting time" answer sends the tab
    watched = [n for n in rules.tracked_names() if rules.limits(n)]
    out: dict[str, dict] = {}
    for cat in watched:
        counts: dict[str, int] = defaultdict(int)
        for x in sessions([s for s in spans if s["category"] == cat]):
            prev = None
            for s in spans:
                if s["end"] > x["start"]:
                    break
                if s["category"] != cat and x["start"] - s["end"] <= lookback and s["seconds"] >= 2:
                    prev = s
            name = "Came back to the Mac" if prev is None else (
                "Straight back after stopping" if prev["category"] in own else prev["category"])
            counts[name] += 1
        total = sum(counts.values())
        rows = sorted(counts.items(), key=lambda kv: -kv[1])
        out[cat] = {"total": total,
                    "from": [{"name": k, "count": v, "pct": round(100 * v / total)} for k, v in rows]}
    return {"days": days, "categories": out}
