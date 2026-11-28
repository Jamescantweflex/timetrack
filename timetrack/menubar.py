"""What the menu-bar item shows. Pure function of today's summary, so it is testable;
menubar.js only draws what this returns."""
from __future__ import annotations

import time
from datetime import datetime

from .rollup import fmt_hm


def build(summary: dict, limits: dict, interrupts: dict, meta: dict, now: float | None = None) -> dict:
    """summary: rollup.summary(); limits: {category: limits}; meta: the meta table as a dict."""
    now = now if now is not None else time.time()
    by = {c["category"]: c for c in summary.get("categories", [])}
    watched = [n for n in limits if limits[n]]
    lines, watched_seconds, over = [], 0, False
    for name in watched:
        c = by.get(name, {"seconds": 0, "opens": 0})
        watched_seconds += c["seconds"]
        budget = int(limits[name].get("daily_minutes") or 0)
        line = f"{name}   {fmt_hm(c['seconds'])}"
        if budget:
            line += f" of {budget}m"
            if c["seconds"] >= budget * 60:
                over = True
                line += "  (over)"
        opens = c.get("opens", 0)
        line += f"   ·   {opens} open{'' if opens == 1 else 's'}"
        lines.append(line)
    if not watched:
        lines.append("Nothing on the watch list yet")
    lines.append(f"All screen time   {fmt_hm(summary.get('total_seconds', 0))}")

    instead = str(interrupts.get("instead") or "").strip()
    if instead:
        lines.append(f"Instead: {instead}")

    try:
        until = int(meta.get("snooze_until") or 0)
    except ValueError:
        until = 0
    snoozed = until > now
    enabled = bool(interrupts.get("enabled", True))
    if not enabled:
        state, symbol = "off", "pause.circle"
        lines.append("Pause screens are switched off")
    elif snoozed:
        state, symbol = "snoozed", "moon.zzz"
        lines.append("Snoozed until " + datetime.fromtimestamp(until).strftime("%H:%M"))
    elif over:
        state, symbol = "over", "exclamationmark.circle"
    else:
        state, symbol = "ok", "hourglass"
    return {"title": fmt_hm(watched_seconds), "symbol": symbol, "state": state,
            "lines": lines, "snoozed": snoozed}
