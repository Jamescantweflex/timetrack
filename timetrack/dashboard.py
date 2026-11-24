"""Local dashboard: stdlib HTTP server, one page, JSON API. http://127.0.0.1:8765"""
from __future__ import annotations

import json
import re
import logging
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import db, phone, rollup
from .rules import CONFIG_PATH, Rules, load as load_config

log = logging.getLogger("timetrack.dashboard")
HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"
ICON_PATH = Path(__file__).resolve().parent / "icon.png"
MANIFEST = {"name": "TimeTrack", "short_name": "TimeTrack", "start_url": "/", "display": "standalone",
            "background_color": "#fcfcfb", "theme_color": "#2a78d6",
            "icons": [{"src": "/icon.png", "sizes": "512x512", "type": "image/png"}]}

_lock = threading.Lock()


def _date(qs: dict, key: str = "date") -> date:
    v = qs.get(key, [None])[0]
    return date.fromisoformat(v) if v else date.today()


LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def _host_ok(host: str | None) -> bool:
    """Only answer requests addressed to this machine by name. Defeats DNS
    rebinding, where a web page points its own hostname at 127.0.0.1 and reads
    our data through it."""
    if not host:
        return False
    h = host.strip().lower()
    if h.startswith("["):                      # [::1]:8765
        h = h.split("]")[0] + "]"
    else:
        h = h.split(":")[0]
    return h in LOCAL_HOSTS


def _same_site(headers) -> bool:
    """A browser page on another origin may not read or change anything.
    Sec-Fetch-Site is set by every current browser; Origin is set on POSTs."""
    sfs = headers.get("Sec-Fetch-Site")
    if sfs and sfs not in ("same-origin", "none"):
        return False
    origin = headers.get("Origin")
    if origin and origin != "null":
        try:
            if not _host_ok(urlsplit(origin).netloc):
                return False
        except ValueError:
            return False
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "TimeTrack/0.1"

    def _guard(self, write: bool = False) -> bool:
        if not _host_ok(self.headers.get("Host")) or not _same_site(self.headers):
            self._json({"error": "forbidden"}, 403)
            return False
        if write and self.headers.get("X-TimeTrack") != "1":
            # Custom header: a page on another site can't add it without a
            # CORS preflight, which we never approve.
            self._json({"error": "forbidden"}, 403)
            return False
        return True

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

    def do_POST(self):
        if not self._guard(write=True):
            return
        u = urlsplit(self.path)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/config":
                with _lock:
                    cfg = validate_config(body, load_config())
                    save_config(cfg)
                    conn = db.connect()
                    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('setup_done','1')")
                    conn.commit(); conn.close()
                log.info("config saved from dashboard: %d categories", len(cfg["categories"]))
                self._json({"ok": True, "config": cfg})
            else:
                self._json({"error": "not found"}, 404)
        except (ValueError, TypeError, KeyError) as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:
            log.exception("POST failed")
            self._json({"error": str(e)}, 500)

    def do_GET(self):
        if not self._guard():
            return
        u = urlsplit(self.path)
        qs = parse_qs(u.query)
        try:
            static = {"/": (HTML_PATH.read_bytes, "text/html; charset=utf-8"),
                      "/icon.png": (ICON_PATH.read_bytes, "image/png"),
                      "/manifest.json": (lambda: json.dumps(MANIFEST).encode(), "application/manifest+json")}
            if u.path in static:
                read, ctype = static[u.path]
                body = read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
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
                    meta = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM meta")}
                    done = meta.get("instead_done_date") == d.isoformat() or meta.get("meditated_date") == d.isoformat()
                    s["instead_done_today"] = done if d == date.today() else None
                    s["setup_done"] = meta.get("setup_done") == "1"
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
                elif u.path == "/api/config":
                    self._json(load_config())
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


def _clean_list(v, lower=False):
    if isinstance(v, str):
        v = v.replace("\n", ",").split(",")
    out = []
    for x in v or []:
        x = re.sub(r'[<>"\\\x00-\x1f]', "", str(x)).strip()
        if lower:
            x = x.lower()
            if x.startswith("www."):
                x = x[4:]
        if x and x not in out:
            out.append(x)
    return out


def validate_config(new: dict, current: dict) -> dict:
    """Accept only the fields the settings panel edits; keep everything else as is."""
    cfg = json.loads(json.dumps(current))
    it = new.get("interrupts", {})
    cur_it = cfg.setdefault("interrupts", {})
    for key, lo, hi in (("pause_seconds", 0, 120), ("grace_minutes", 1, 240), ("extension_minutes", 1, 240),
                        ("timeout_seconds", 10, 600), ("digest_hour", 0, 23)):
        if key in it:
            cur_it[key] = max(lo, min(hi, int(it[key])))
    for key in ("enabled", "instead_gate"):
        if key in it:
            cur_it[key] = bool(it[key])
    if "instead" in it:
        cur_it["instead"] = str(it["instead"] or "").strip()[:120]
    cur_it.pop("meditation_gate", None)
    if "categories" in new:
        cats = {}
        for name, spec in new["categories"].items():
            name = re.sub(r'[<>"\\\x00-\x1f]', "", str(name)).strip()[:40]
            if not name:
                continue
            c = {
                "domains": _clean_list(spec.get("domains"), lower=True),
                "apps": _clean_list(spec.get("apps")),
                "phone_apps": _clean_list(spec.get("phone_apps")),
                "passive": bool(spec.get("passive")),
            }
            instead = str(spec.get("instead") or "").strip()[:120]
            if instead:
                c["instead"] = instead
            if not (c["domains"] or c["apps"] or c["phone_apps"]):
                continue
            lim = spec.get("limits")
            if lim:
                c["limits"] = {
                    "pause_on_open": bool(lim.get("pause_on_open", True)),
                    "session_minutes": max(0, min(600, int(lim.get("session_minutes") or 0))),
                    "daily_minutes": max(0, min(1440, int(lim.get("daily_minutes") or 0))),
                    "block_after_daily": bool(lim.get("block_after_daily")),
                }
            cats[name] = c
        if not cats:
            raise ValueError("at least one category is required")
        cfg["categories"] = cats
    return cfg


def save_config(cfg: dict) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n")
    tmp.replace(CONFIG_PATH)


def serve(port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log.info("dashboard on http://127.0.0.1:%d", port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
