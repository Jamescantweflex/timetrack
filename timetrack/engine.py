"""Interrupt state machine. Pure: no clock, no UI, no database. Fully testable.

Feed it `tick(now, category, today_seconds)` every few seconds. It returns a
Prompt to show, or None. Report the user's answer with `answer(...)`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Prompt:
    kind: str              # "pause" | "session" | "daily"
    category: str
    session_seconds: int
    today_seconds: int
    limit: dict
    block: bool = False    # only "Done" allowed


@dataclass
class CatState:
    last_seen: int = 0
    session_start: int = 0
    allowed_until: int | None = None   # after "go"/"more": leave me alone until then
    last_prompt: int = 0
    daily_prompted: bool = False


class Engine:
    def __init__(self, limits: dict[str, dict], settings: dict):
        self.limits = limits                       # category -> limits dict
        self.gap = int(settings.get("session_gap_seconds", 60))
        self.grace = int(settings.get("grace_minutes", 10)) * 60
        self.extension = int(settings.get("extension_minutes", 5)) * 60
        self.cooldown = 20                         # never two prompts within 20 s
        self.state: dict[str, CatState] = {}
        self.open_prompt: Prompt | None = None

    def _st(self, cat: str) -> CatState:
        return self.state.setdefault(cat, CatState())

    def new_day(self) -> None:
        for s in self.state.values():
            s.daily_prompted = False

    def tick(self, now: int, category: str | None, today_seconds: int = 0) -> Prompt | None:
        # If a prompt is up and the user has wandered off that category for a
        # whole gap, the prompt is stale: the caller should close it as "left".
        if self.open_prompt is not None:
            st = self._st(self.open_prompt.category)
            if category == self.open_prompt.category:
                st.last_seen = now
            return None

        if category is None or category not in self.limits:
            return None
        lim = self.limits[category]
        st = self._st(category)

        # Right after a prompt, leave things alone (and don't start a session
        # yet, so a quick return after "Not now" still gets the pause screen).
        if now - st.last_prompt < self.cooldown:
            return None

        new_session = now - st.last_seen > self.gap
        if new_session:
            st.session_start = now
            st.allowed_until = None
        st.last_seen = now
        session_seconds = now - st.session_start

        daily_limit = int(lim.get("daily_minutes", 0) or 0) * 60
        over_daily = daily_limit and today_seconds >= daily_limit
        block = bool(lim.get("block_after_daily")) and over_daily

        if new_session and lim.get("pause_on_open"):
            kind = "daily" if over_daily else "pause"
            return self._emit(Prompt(kind, category, session_seconds, today_seconds, lim, block), now)

        # Past the explicit allowance given at the last prompt?
        if st.allowed_until is not None:
            if now >= st.allowed_until:
                kind = "daily" if over_daily else "session"
                return self._emit(Prompt(kind, category, session_seconds, today_seconds, lim, block), now)
            return None

        # No allowance in force: natural session limit.
        session_limit = int(lim.get("session_minutes", 0) or 0) * 60
        if session_limit and session_seconds >= session_limit:
            kind = "daily" if over_daily else "session"
            return self._emit(Prompt(kind, category, session_seconds, today_seconds, lim, block), now)

        if over_daily and not st.daily_prompted:
            st.daily_prompted = True
            return self._emit(Prompt("daily", category, session_seconds, today_seconds, lim, block), now)
        return None

    def _emit(self, p: Prompt, now: int) -> Prompt:
        self.open_prompt = p
        self._st(p.category).last_prompt = now
        return p

    def stale_prompt(self, now: int) -> bool:
        """True when the open prompt's category hasn't been seen for a whole gap."""
        if self.open_prompt is None:
            return False
        return now - self._st(self.open_prompt.category).last_seen > self.gap

    def answer(self, now: int, choice: str) -> None:
        """choice: go | more | bounce | done | timeout | instead | left  (meditate = old name for instead)"""
        p = self.open_prompt
        if p is None:
            return
        st = self._st(p.category)
        self.open_prompt = None
        st.last_prompt = now
        if choice == "go":
            st.allowed_until = now + self.grace
        elif choice == "more":
            st.allowed_until = now + self.extension
        else:  # bounce / done / left: next sighting after the gap is a new session
            st.allowed_until = None
            if choice in ("bounce", "done", "timeout", "instead", "meditate"):
                st.last_seen = 0
