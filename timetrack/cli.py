"""python -m timetrack <command>

  collect   run the Mac collector (foreground; launchd runs this)
  serve     run the dashboard on http://127.0.0.1:8765
  ingest    pull new iPhone events from iCloud Drive now
  report    print today's (or --date YYYY-MM-DD) summary to the terminal
  status    is the collector alive? last span? db size?
  interrupt run the interrupter (pause screens, limits; launchd runs this)
  demo      show the pause screen once with fake numbers (--kind pause|session|daily)
  decisions print recent pause-screen answers
  snooze N  no pause screens for N minutes (0 = cancel). For meetings, screen shares.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from . import db, phone, rollup
from .rules import Rules


def cmd_report(args) -> None:
    conn = db.connect()
    rules = Rules()
    phone.ingest(conn)
    d = date.fromisoformat(args.date) if args.date else date.today()
    s = rollup.summary(conn, d, rules)
    print(f"{d.isoformat()}  total tracked {rollup.fmt_hm(s['total_seconds'])}")
    print(f"{'category':<28}{'time':>9}{'opens':>7}{'mac':>9}{'phone':>9}")
    for c in s["categories"][: args.top]:
        print(f"{c['category'][:27]:<28}{rollup.fmt_hm(c['seconds']):>9}{c['opens']:>7}"
              f"{rollup.fmt_hm(c['mac']):>9}{rollup.fmt_hm(c['phone']):>9}")
    if args.sessions:
        print("\nsessions for tracked categories:")
        for x in s["sessions"]:
            if x["category"] in s["tracked"]:
                t0 = datetime.fromtimestamp(x["start"]).strftime("%H:%M")
                print(f"  {t0}  {x['category']:<10}{rollup.fmt_hm(x['seconds']):>7}  {x['source']}"
                      + (f"  {x['titles'][0][:60]}" if x["titles"] else ""))


def cmd_status(args) -> None:
    conn = db.connect()
    r = conn.execute("SELECT * FROM spans WHERE source='mac' ORDER BY end DESC LIMIT 1").fetchone()
    n = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
    print(f"db: {db.DB_PATH} ({db.DB_PATH.stat().st_size // 1024} KB, {n} spans)")
    if r:
        age = int(datetime.now().timestamp()) - r["end"]
        alive = "ALIVE" if age < 30 else f"STALE ({age}s since last heartbeat)"
        print(f"collector: {alive}")
        print(f"last span: {r['app']} {r['domain'] or ''} {(r['title'] or '')[:50]!r} "
              f"{datetime.fromtimestamp(r['start']).strftime('%H:%M:%S')}-"
              f"{datetime.fromtimestamp(r['end']).strftime('%H:%M:%S')} [{r['end_kind']}]")
    else:
        print("collector: no spans yet")
    log_path = Path.home() / "Library" / "Logs" / "TimeTrack" / "interrupter.log"
    if log_path.exists():
        tail = log_path.read_text().strip().splitlines()[-1:] or [""]
        print(f"interrupter: last log line: {tail[0][:100]}")
    z = conn.execute("SELECT value FROM meta WHERE key='snooze_until'").fetchone()
    if z and int(z["value"] or 0) > datetime.now().timestamp():
        print(f"interrupts: SNOOZED until {datetime.fromtimestamp(int(z['value'])).strftime('%H:%M')}")
    p = phone.EVENTS_PATH
    print(f"phone file: {p} {'exists' if p.exists() else 'MISSING (set up the iPhone shortcut)'}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="timetrack", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect")
    sp = sub.add_parser("serve")
    sp.add_argument("--port", type=int, default=8765)
    sub.add_parser("ingest")
    rp = sub.add_parser("report")
    rp.add_argument("--date")
    rp.add_argument("--top", type=int, default=15)
    rp.add_argument("--sessions", action="store_true")
    sub.add_parser("status")
    sub.add_parser("interrupt")
    dp = sub.add_parser("demo")
    dp.add_argument("--kind", default="pause", choices=["pause", "session", "daily"])
    sub.add_parser("decisions")
    zp = sub.add_parser("snooze")
    zp.add_argument("minutes", type=int)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)

    if args.cmd == "collect":
        from .collector import main as collect_main
        collect_main()
    elif args.cmd == "serve":
        from .dashboard import serve
        serve(args.port)
    elif args.cmd == "ingest":
        n = phone.ingest(db.connect())
        print(f"{n} new phone events")
    elif args.cmd == "report":
        cmd_report(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "interrupt":
        from .interrupter import main as interrupt_main
        interrupt_main()
    elif args.cmd == "demo":
        from .interrupter import demo
        demo(args.kind)
    elif args.cmd == "snooze":
        import time as _t
        until = int(_t.time()) + args.minutes * 60 if args.minutes > 0 else 0
        db.connect().execute("INSERT OR REPLACE INTO meta(key,value) VALUES('snooze_until',?)", (str(until),))
        print("interrupts snoozed until " + datetime.fromtimestamp(until).strftime("%H:%M") if until else "snooze cancelled")
    elif args.cmd == "decisions":
        conn = db.connect()
        for r in conn.execute("SELECT * FROM decisions ORDER BY ts DESC LIMIT 30"):
            print(datetime.fromtimestamp(r["ts"]).strftime("%a %H:%M"), f"{r['category']:<9}{r['kind']:<8}{r['choice']:<7}",
                  f"sitting {r['session_seconds']//60}m today {r['today_seconds']//60}m", f"  {r['intention']}" if r["intention"] else "")
