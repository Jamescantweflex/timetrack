"""The interrupter: watches what the collector is recording and steps in.

Runs as its own launchd agent. A hidden Tk root drives a 2-second tick. When the
engine says so, a full-screen pause window appears over the feed. Answers are
logged to the decisions table; "Not now"/"Done" sends the browser tab to the
dashboard instead.
"""
from __future__ import annotations

import logging
import subprocess
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime, timedelta

from . import db, rollup
from .engine import Engine, Prompt
from .rules import Rules

log = logging.getLogger("timetrack.interrupter")

TICK_MS = 1000
RECENT = 12          # a span heartbeat older than this means "not in front any more"
CHROMIUM = {"Arc", "Google Chrome", "Brave Browser", "Microsoft Edge"}

REDIRECT_CHROMIUM = '''
tell application "%s"
    repeat with w in windows
        try
            set URL of active tab of w to "%s"
            exit repeat
        end try
    end repeat
end tell
'''
REDIRECT_SAFARI = 'tell application "Safari" to set URL of current tab of front window to "%s"'
URL_CHROMIUM = '''
tell application "%s"
    repeat with w in windows
        try
            return URL of active tab of w
        end try
    end repeat
end tell
return ""
'''
URL_SAFARI = 'tell application "Safari" to return URL of current tab of front window'


def osa(script: str, timeout: float = 8) -> bool:
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("osascript timed out")
        return False
    if r.returncode != 0:
        log.warning("osascript: %s", r.stderr.strip()[:160])
    return r.returncode == 0


def notify(title: str, body: str) -> None:
    body = body.replace('"', "'")
    osa(f'display notification "{body}" with title "{title}"')


def bring_to_front() -> None:
    try:
        r = subprocess.run(["osascript", "-e", 'tell application "System Events" to set frontmost of process "Python" to true'],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            log.warning("bring_to_front: %s", r.stderr.strip()[:160])
    except subprocess.TimeoutExpired:
        log.warning("bring_to_front timed out")


def osa_out(script: str, timeout: float = 8) -> str:
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except subprocess.TimeoutExpired:
        return ""


def redirect_tab(app: str, url: str, still_there) -> None:
    """Send the browser's active tab to `url`, but only if still_there(current_url) agrees."""
    if app in CHROMIUM:
        cur = osa_out(URL_CHROMIUM % app)
        if still_there(cur):
            osa(REDIRECT_CHROMIUM % (app, url))
        else:
            log.info("no redirect: active tab is %s", cur[:80])
    elif app == "Safari":
        cur = osa_out(URL_SAFARI)
        if still_there(cur):
            osa(REDIRECT_SAFARI % url)


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
BG, FG, MUTED, ACCENT, DANGER = "#141414", "#f2f1ed", "#9a9892", "#3987e5", "#e66767"


class PauseWindow:
    """Full-screen, topmost. Calls on_answer(choice, intention) exactly once."""

    def __init__(self, root: tk.Tk, prompt: Prompt, pause_seconds: int, grace_min: int, ext_min: int,
                 opens_today: int, on_answer):
        self.on_answer = on_answer
        self.answered = False
        self.p = prompt
        self.remaining = pause_seconds if prompt.kind == "pause" else 3
        self.grace_min, self.ext_min = grace_min, ext_min

        self.top = tk.Toplevel(root, bg=BG)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-topmost", True)
        self.top.protocol("WM_DELETE_WINDOW", lambda: None)
        self.top.bind("<Escape>", lambda e: self._choose(self._secondary_choice()))
        self.top.bind("<Return>", lambda e: self._primary_if_ready())

        big = tkfont.Font(family="Helvetica Neue", size=44, weight="bold")
        mid = tkfont.Font(family="Helvetica Neue", size=20)
        small = tkfont.Font(family="Helvetica Neue", size=15)
        btn = tkfont.Font(family="Helvetica Neue", size=17, weight="bold")

        f = tk.Frame(self.top, bg=BG)
        f.place(relx=0.5, rely=0.5, anchor="center")

        cat = prompt.category
        sess = rollup.fmt_hm(prompt.session_seconds)
        today = rollup.fmt_hm(prompt.today_seconds)
        budget = prompt.limit.get("daily_minutes")
        if prompt.kind == "pause":
            head = f"You just opened {cat}."
            sub = f"Today so far: {today} across {opens_today} open{'s' if opens_today != 1 else ''}."
        elif prompt.kind == "session":
            head = f"{sess} on {cat} this sitting."
            sub = f"Today: {today}" + (f" of your {budget}m budget." if budget else ".")
        else:
            head = f"Past today's {cat} budget."
            sub = f"{today} used of {budget}m. This sitting: {sess}."

        tk.Label(f, text=head, font=big, fg=FG, bg=BG, wraplength=900, justify="center").pack(pady=(0, 10))
        tk.Label(f, text=sub, font=mid, fg=MUTED, bg=BG).pack(pady=(0, 36))

        self.intent = None
        if prompt.kind == "pause":
            tk.Label(f, text="What are you here for?", font=small, fg=FG, bg=BG).pack()
            self.intent = tk.Entry(f, font=mid, width=36, justify="center", relief="flat",
                                   bg="#232323", fg=FG, insertbackground=FG)
            self.intent.pack(ipady=8, pady=(8, 30))
            self.intent.focus_set()

        self.count = tk.Label(f, text="", font=mid, fg=MUTED, bg=BG)
        self.count.pack(pady=(0, 18))

        row = tk.Frame(f, bg=BG)
        row.pack()
        primary_text = {"pause": f"Go in · {grace_min} min", "session": f"{ext_min} more minutes",
                        "daily": f"Override · {ext_min} min"}[prompt.kind]
        secondary_text = {"pause": "Not now", "session": "Done", "daily": "Done"}[prompt.kind]

        self.btn_secondary = tk.Button(row, text=secondary_text, font=btn, command=lambda: self._choose(self._secondary_choice()),
                                       highlightbackground=BG, padx=22, pady=10)
        self.btn_secondary.pack(side="left", padx=12)
        self.btn_primary = tk.Button(row, text=primary_text, font=btn, command=self._primary_if_ready,
                                     highlightbackground=BG, padx=22, pady=10, state="disabled")
        if not prompt.block:
            self.btn_primary.pack(side="left", padx=12)
        else:
            tk.Label(f, text="Budget spent for today. Hard mode is on.", font=small, fg=DANGER, bg=BG).pack(pady=(14, 0))

        tk.Label(f, text="Esc = " + secondary_text + "    Enter = " + primary_text, font=small, fg=MUTED, bg=BG).pack(pady=(30, 0))

        self.top.lift()
        self.top.focus_force()
        if self.intent is None:
            # Keys only arrive if some widget holds focus: use the Done button.
            self.btn_secondary.configure(takefocus=1)
            self.btn_secondary.focus_set()
            self.top.after(400, self.btn_secondary.focus_force)
        self.top.bind_all("<Escape>", lambda e: self._choose(self._secondary_choice()))
        self.top.bind_all("<Return>", lambda e: self._primary_if_ready())
        # A Tk window from a background agent doesn't always win focus on its
        # own. Ask the system to bring Python forward, twice to be safe.
        for delay in (150, 1200):
            self.top.after(delay, bring_to_front)
        self._countdown()

    def _secondary_choice(self) -> str:
        return "bounce" if self.p.kind == "pause" else "done"

    def _primary_choice(self) -> str:
        return "go" if self.p.kind == "pause" else "more"

    def _countdown(self):
        if self.answered:
            return
        if self.remaining > 0:
            self.count.config(text=f"Breathe. {self.remaining}")
            self.remaining -= 1
            self.top.after(1000, self._countdown)
        else:
            self.count.config(text="")
            if not self.p.block:
                self.btn_primary.config(state="normal")

    def _primary_if_ready(self):
        if self.remaining <= 0 and not self.p.block:
            self._choose(self._primary_choice())

    def _choose(self, choice: str):
        if self.answered:
            return
        self.answered = True
        intention = self.intent.get().strip() if self.intent is not None else None
        try:
            self.top.unbind_all("<Escape>")
            self.top.unbind_all("<Return>")
            self.top.destroy()
        except tk.TclError:
            pass
        self.on_answer(choice, intention or None)

    def close(self, choice: str = "left"):
        self._choose(choice)


# ----------------------------------------------------------------------------
# Loop
# ----------------------------------------------------------------------------
class Interrupter:
    def __init__(self):
        self.conn = db.connect()
        self.rules = Rules()
        self.settings = self.rules.interrupts
        self.engine = Engine({c: self.rules.limits(c) for c in self.rules.tracked_names() if self.rules.limits(c)},
                             self.settings)
        self.root = tk.Tk()
        self.root.withdraw()
        self.window: PauseWindow | None = None
        self.current_app: str | None = None
        self.prompt_app: str | None = None      # browser that was in front when the prompt appeared
        self.last_cat: str | None = None
        self.today = date.today()
        self._summary_cache = (0, None)
        self._config_mtime = 0.0
        self._last_tick = 0.0

    # -- data ---------------------------------------------------------------
    def current(self) -> tuple[str | None, str | None]:
        """(category, app) of what is in front right now, from the collector's latest span."""
        now = int(time.time())
        r = self.conn.execute(
            "SELECT app, domain, end FROM spans WHERE source='mac' ORDER BY end DESC, id DESC LIMIT 1").fetchone()
        if not r or now - r["end"] > RECENT:
            return None, None
        return self.rules.categorise("mac", r["app"], r["domain"]), r["app"]

    def today_summary(self) -> dict:
        now = time.time()
        ts, s = self._summary_cache
        if s is None or now - ts > 10:
            s = rollup.summary(self.conn, date.today(), self.rules)
            self._summary_cache = (now, s)
        return s

    def today_for(self, cat: str) -> tuple[int, int]:
        s = self.today_summary()
        for c in s["categories"]:
            if c["category"] == cat:
                return c["seconds"], c["opens"]
        return 0, 0

    def reload_config_if_changed(self):
        try:
            m = __import__("os").path.getmtime(self.rules.__class__.__module__ and
                                               __import__("timetrack.rules", fromlist=["CONFIG_PATH"]).CONFIG_PATH)
        except OSError:
            return
        if m != self._config_mtime:
            self._config_mtime = m
            self.rules = Rules()
            self.settings = self.rules.interrupts
            self.engine.limits = {c: self.rules.limits(c) for c in self.rules.tracked_names() if self.rules.limits(c)}
            self.engine.gap = int(self.settings.get("session_gap_seconds", 60))
            self.engine.grace = int(self.settings.get("grace_minutes", 10)) * 60
            self.engine.extension = int(self.settings.get("extension_minutes", 5)) * 60
            log.info("config loaded: limits for %s, enabled=%s", list(self.engine.limits), self.settings.get("enabled", True))

    # -- actions ------------------------------------------------------------
    def record(self, p: Prompt, choice: str, intention: str | None):
        self.conn.execute(
            "INSERT INTO decisions(ts,category,kind,choice,intention,session_seconds,today_seconds) VALUES(?,?,?,?,?,?,?)",
            (int(time.time()), p.category, p.kind, choice, intention, p.session_seconds, p.today_seconds))

    def on_answer(self, p: Prompt, choice: str, intention: str | None):
        now = int(time.time())
        self.window = None
        self.engine.answer(now, choice)
        self.record(p, choice, intention)
        log.info("%s/%s -> %s %s", p.category, p.kind, choice, f"({intention})" if intention else "")
        if choice in ("go", "more") and self.prompt_app:
            # Hand focus back to the browser; a window-less Python app stays "active" otherwise.
            osa(f'tell application "{self.prompt_app}" to activate', timeout=4)
        if choice in ("bounce", "done") and self.prompt_app:
            from .rules import domain_of
            cat = p.category
            rules = self.rules
            redirect_tab(self.prompt_app, self.settings.get("redirect_url", "http://127.0.0.1:8765/"),
                         lambda u: rules.categorise("mac", self.prompt_app, domain_of(u)) == cat)
            osa(f'tell application "{self.prompt_app}" to activate', timeout=4)

    def show(self, p: Prompt):
        _, opens = self.today_for(p.category)
        self.prompt_app = self.current_app
        log.info("prompt %s/%s (app %s, sitting %ss, today %ss)", p.category, p.kind, self.prompt_app,
                 p.session_seconds, p.today_seconds)
        self.window = PauseWindow(self.root, p, int(self.settings.get("pause_seconds", 10)),
                                  int(self.settings.get("grace_minutes", 10)), int(self.settings.get("extension_minutes", 5)),
                                  opens, lambda choice, intention: self.on_answer(p, choice, intention))

    # -- digest -------------------------------------------------------------
    def maybe_digest(self):
        hour = int(self.settings.get("digest_hour", 8))
        today = date.today()
        if today != self.today:
            self.today = today
            self.engine.new_day()
        if datetime.now().hour < hour:
            return
        last = self.conn.execute("SELECT value FROM meta WHERE key='digest_date'").fetchone()
        if last and last["value"] == today.isoformat():
            return
        y = today - timedelta(days=1)
        s = rollup.summary(self.conn, y, self.rules)
        parts = []
        for c in s["categories"]:
            if c["category"] in self.engine.limits and (c["seconds"] or c["opens"]):
                parts.append(f"{c['category']} {rollup.fmt_hm(c['seconds'])} ({c['opens']} opens)")
        d0, d1 = rollup.day_bounds(y)
        row = self.conn.execute("SELECT SUM(choice='bounce') b, SUM(choice='go') g FROM decisions WHERE ts>=? AND ts<?", (d0, d1)).fetchone()
        if row and (row["b"] or row["g"]):
            parts.append(f"bounced {row['b'] or 0}, went in {row['g'] or 0}")
        body = " · ".join(parts) if parts else "nothing tracked"
        notify(f"Yesterday ({y.strftime('%a')})", body)
        self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('digest_date',?)", (today.isoformat(),))
        log.info("digest sent: %s", body)

    # -- tick ---------------------------------------------------------------
    def tick(self):
        t = time.time()
        if self._last_tick and t - self._last_tick > 2.5:
            log.warning("slow tick: %.1fs since last (App Nap?)", t - self._last_tick)
        self._last_tick = t
        try:
            self.reload_config_if_changed()
            now = int(time.time())
            cat, app = self.current()
            if app:
                self.current_app = app
            if cat != self.last_cat:
                log.debug("front: %s (%s)", cat, app)
                self.last_cat = cat
            today_seconds = self.today_for(cat)[0] if cat else 0
            enabled = self.settings.get("enabled", True)
            if enabled:
                z = self.conn.execute("SELECT value FROM meta WHERE key='snooze_until'").fetchone()
                if z and int(z["value"] or 0) > now:
                    enabled = False
            if self.window is not None:
                self.engine.tick(now, cat, today_seconds)
                if app and app != "Python":          # something got in front of us: come back
                    bring_to_front()
                if self.engine.stale_prompt(now):
                    log.info("prompt abandoned (left %s)", self.engine.open_prompt.category)
                    self.window.close("left")
            elif enabled:
                p = self.engine.tick(now, cat, today_seconds)
                if p:
                    self.show(p)
            self.maybe_digest()
        except Exception:
            log.exception("tick failed")
        finally:
            self.root.after(TICK_MS, self.tick)

    def run(self):
        log.info("interrupter started")
        self.root.after(500, self.tick)
        self.root.mainloop()


def demo(kind: str = "pause") -> None:
    """Show the pause window once with fake numbers, without touching the engine."""
    root = tk.Tk(); root.withdraw()
    p = Prompt(kind, "X", 11 * 60 + 20, 27 * 60, {"daily_minutes": 30, "session_minutes": 10}, block=False)

    def done(choice, intention):
        print("choice:", choice, "intention:", intention)
        root.after(200, root.destroy)
    PauseWindow(root, p, 10, 10, 5, 4, done)
    root.mainloop()


def main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    Interrupter().run()
