"""Local dashboard: stdlib HTTP server, one page, JSON API. http://127.0.0.1:8765"""
from __future__ import annotations

import json
import logging
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import db, phone, rollup
from .rules import Rules

log = logging.getLogger("timetrack.dashboard")
HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"

_lock = threading.Lock()


def _date(qs: dict, key: str = "date") -> date:
    v = qs.get(key, [None])[0]
    return date.fromisoformat(v) if v else date.today()


class Handler(BaseHTTPRequestHandler):
    server_version = "TimeTrack/0.1"

    def log_message(self, fmt, *args):  # quieter
        log.debug(fmt, *args)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlsplit(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path == "/":
                body = HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            with _lock:
                conn = db.connect()
                rules = Rules()  # re-read each request so config edits show up live
                try:
                    phone.ingest(conn)
                except Exception:
                    log.exception("phone ingest failed")
                if u.path == "/api/day":
                    d = _date(qs)
                    s = rollup.summary(conn, d, rules)
                    h = rollup.hourly(conn, d, rules, s["tracked"])
                    s["hours"] = h["hours"]
                    s["order"] = rules.tracked_names()
                    s["passive"] = [c for c in rules.tracked_names() if rules.is_passive(c)]
                    s["limits"] = {c: rules.limits(c) for c in rules.tracked_names() if rules.limits(c)}
                    d0, d1 = rollup.day_bounds(d)
                    s["decisions"] = [dict(r) for r in conn.execute(
                        "SELECT ts,category,kind,choice,intention,session_seconds,today_seconds FROM decisions "
                        "WHERE ts>=? AND ts<? ORDER BY ts DESC", (d0, d1))]
                    s["interrupts_enabled"] = bool(rules.interrupts.get("enabled", True))
                    self._json(s)
                elif u.path == "/api/week":
                    end = _date(qs, "end")
                    self._json({"days": rollup.week(conn, end, rules, int(qs.get("days", ["7"])[0])),
                                "order": rules.tracked_names()})
                elif u.path == "/api/decisions":
                    days = int(qs.get("days", ["7"])[0])
                    d0, _ = rollup.day_bounds(date.today() - timedelta(days=days - 1))
                    rows = conn.execute("SELECT date(ts,'unixepoch','localtime') d, category, choice, COUNT(*) n "
                                        "FROM decisions WHERE ts>=? GROUP BY 1,2,3", (d0,)).fetchall()
                    self._json({"rows": [dict(r) for r in rows]})
                elif u.path == "/api/status":
                    r = conn.execute("SELECT end FROM spans WHERE source='mac' ORDER BY end DESC LIMIT 1").fetchone()
                    import time
                    age = int(time.time()) - r["end"] if r else None
                    self._json({"collector_alive": age is not None and age < 30, "last_heartbeat_age": age,
                                "phone_file": str(phone.EVENTS_PATH), "phone_file_exists": phone.EVENTS_PATH.exists()})
                else:
                    self._json({"error": "not found"}, 404)
                conn.close()
        except Exception as e:
            log.exception("request failed")
            self._json({"error": str(e)}, 500)


def serve(port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log.info("dashboard on http://127.0.0.1:%d", port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
