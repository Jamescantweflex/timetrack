"""Mac collector: polls the frontmost app and browser tab, writes spans.

One open span at a time. Each poll either extends it (heartbeat) or closes it
and opens a new one. Idle, screen lock and process exit all close the span
honestly so gaps show as gaps.
"""
from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

from . import db
from .rules import Rules, domain_of

log = logging.getLogger("timetrack.collector")

POLL_SECONDS = 5
IDLE_ACTIVE_SECONDS = 180        # no input for 3 min -> stop counting
IDLE_PASSIVE_SECONDS = 3600      # ...unless watching video: allow 60 min
GAP_SECONDS = 3 * POLL_SECONDS   # wall-clock jump bigger than this = Mac slept

FRONT_APP_SCRIPT = r"""
tell application "System Events" to get name of first application process whose frontmost is true
"""

WINDOW_TITLE_SCRIPT = r"""
tell application "System Events"
    tell (first application process whose frontmost is true)
        return name of front window
    end tell
end tell
"""

# Arc, Chrome, Brave and Edge share Chrome's AppleScript dictionary. Arc's first
# window is often hidden with no active tab, so walk the windows.
CHROMIUM_SCRIPT = r"""
tell application "%s"
    repeat with w in windows
        try
            return (URL of active tab of w) & "\t" & (title of active tab of w)
        end try
    end repeat
end tell
return ""
"""

SAFARI_SCRIPT = r"""
tell application "Safari"
    return (URL of current tab of front window) & "\t" & (name of current tab of front window)
end tell
"""

CHROMIUM_APPS = {"Arc", "Google Chrome", "Brave Browser", "Microsoft Edge"}


def _osascript(script: str, timeout: float = 10) -> str | None:
    global _backoff_until
    if time.time() < _backoff_until:
        return None
    try:
        out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Usually a macOS "python3 wants to control ..." permission dialog waiting
        # for a click. Back off so we don't stack up dialogs.
        log.warning("osascript timed out (a permission dialog may be waiting for Allow)")
        _backoff_until = time.time() + 60
        return None
    if out.returncode != 0:
        log.warning("osascript error: %s", out.stderr.strip()[:200])
        return None
    return out.stdout.rstrip("\n")


_backoff_until = 0.0


@dataclass
class Front:
    app: str
    url: str | None
    title: str | None


def read_front() -> Front | None:
    app = _osascript(FRONT_APP_SCRIPT)
    if not app:
        return None
    url = title = None
    if app in CHROMIUM_APPS:
        res = _osascript(CHROMIUM_SCRIPT % app)
    elif app == "Safari":
        res = _osascript(SAFARI_SCRIPT)
    else:
        res = None
        t = _osascript(WINDOW_TITLE_SCRIPT, timeout=2)
        title = t or None
    if res:
        parts = res.split("\t", 1)
        url = parts[0] or None
        title = (parts[1] if len(parts) > 1 else "") or None
    return Front(app=app, url=url, title=title)


def read_idle_seconds() -> float:
    try:
        out = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem", "-d", "4"],
            capture_output=True, text=True, timeout=4,
        ).stdout
    except subprocess.TimeoutExpired:
        return 0.0
    for line in out.splitlines():
        if "HIDIdleTime" in line:
            try:
                return int(line.split("=")[-1].strip()) / 1e9
            except ValueError:
                return 0.0
    return 0.0


def screen_locked() -> bool:
    try:
        out = subprocess.run(
            ["ioreg", "-n", "Root", "-d1", "-a"],
            capture_output=True, text=True, timeout=4,
        ).stdout
    except subprocess.TimeoutExpired:
        return False
    # Key is present (and true) only while the screen is locked.
    return "CGSSessionScreenIsLocked" in out


class Collector:
    def __init__(self, conn, rules: Rules, poll: int = POLL_SECONDS):
        self.conn = conn
        self.rules = rules
        self.poll = poll
        self.current_id: int | None = None
        self.current_key: tuple | None = None
        self.current_category: str | None = None
        self.last_tick: float = 0.0
        self.running = True

    # -- span lifecycle -------------------------------------------------
    def _open(self, now: int, f: Front, domain: str | None) -> None:
        cur = self.conn.execute(
            "INSERT INTO spans(source,start,end,app,domain,title,url,end_kind) "
            "VALUES('mac',?,?,?,?,?,?,'open')",
            (now, now, f.app, domain, f.title, f.url),
        )
        self.current_id = cur.lastrowid
        self.current_key = (f.app, domain, f.title)
        self.current_category = self.rules.categorise("mac", f.app, domain)

    def _heartbeat(self, now: int) -> None:
        self.conn.execute("UPDATE spans SET end=? WHERE id=?", (now, self.current_id))

    def _close(self, end: int, kind: str) -> None:
        if self.current_id is None:
            return
        self.conn.execute(
            "UPDATE spans SET end=MAX(start,?), end_kind=? WHERE id=?",
            (end, kind, self.current_id),
        )
        self.current_id = None
        self.current_key = None
        self.current_category = None

    # -- one poll ---------------------------------------------------------
    def tick(self, now: float | None = None) -> None:
        now = int(now if now is not None else time.time())

        # Mac was asleep: the span really ended at the last heartbeat.
        if self.last_tick and now - self.last_tick > GAP_SECONDS:
            self._close(int(self.last_tick), "stop")
        self.last_tick = now

        if screen_locked():
            self._close(now, "lock")
            return

        idle = read_idle_seconds()
        limit = IDLE_PASSIVE_SECONDS if (
            self.current_category and self.rules.is_passive(self.current_category)
        ) else IDLE_ACTIVE_SECONDS
        if idle > limit:
            # Idle began `idle` seconds ago; don't count the idle tail.
            self._close(now - int(idle), "idle")
            return

        f = read_front()
        if f is None or f.app in self.rules.ignore_apps:
            self._close(now, "switch")
            return

        domain = domain_of(f.url) if self.rules.is_browser(f.app) else None
        key = (f.app, domain, f.title)
        if self.current_id is not None and key == self.current_key:
            self._heartbeat(now)
        else:
            self._close(now, "switch")
            self._open(now, f, domain)

    def run(self) -> None:
        def stop(*_):
            self.running = False
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        log.info("collector started, db=%s", db.DB_PATH)
        # Startup self-check: proves the Automation permission works under launchd.
        probe = read_front()
        log.info("startup probe: %s (idle %.0fs, locked %s)", probe, read_idle_seconds(), screen_locked())
        try:
            while self.running:
                try:
                    self.tick()
                except Exception:  # keep running no matter what
                    log.exception("tick failed")
                time.sleep(self.poll)
        finally:
            self._close(int(time.time()), "stop")
            log.info("collector stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    conn = db.connect()
    # Any span left 'open' by a previous crash gets closed where it stood.
    conn.execute("UPDATE spans SET end_kind='stop' WHERE end_kind='open'")
    Collector(conn, Rules()).run()


if __name__ == "__main__":
    main()
