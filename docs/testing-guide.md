# TimeTrack — what to test when you're back

Everything below is already installed and running. Dashboard:
http://127.0.0.1:8765

## 1. Is it alive? (30 seconds)

From `~/Projects/timetrack`:

```bash
python3 -m timetrack status
```

Expect `collector: ALIVE`, an interrupter log line, and the phone file either
present (if you've done the iPhone setup) or MISSING.

## 2. The pause screen (2 minutes)

1. Open x.com in Arc. Within about 5 seconds a full-screen dark screen appears:
   "You just opened X." with today's numbers, a 10-second "Breathe" countdown,
   and a box asking what you're here for.
2. Press **Esc** (or click Not now). The tab is sent to the dashboard with a
   "Good call" banner, and the Pause screens card shows a "Not now" row.
3. Open x.com again (wait 20 seconds first; there's a cooldown). This time wait
   out the countdown, type an intention, press **Enter** (Go in · 10 min).
   You're back on X with no further interruption for 10 minutes.
4. Stay on X past those 10 minutes: "10m on X this sitting" screen, with
   "5 more minutes" or "Done". Done sends you to the dashboard.
5. Get past 30 minutes of X in a day: the screens change to "Past today's X
   budget". Still lets you in ("Override") unless you turn on hard mode.

YouTube behaves the same with 20 minutes per sitting and 45 per day.

What the screen will NOT do: it doesn't appear for X or YouTube inside a
native app on the Mac (there isn't one), and it can't appear on the phone;
see the iPhone guide for the phone-side pause.

Want to see the screens without waiting? `python3 -m timetrack demo --kind
session` (or `daily`). In the demo, click the buttons; keyboard shortcuts are
only reliable in the real thing.

## 3. Things to tune (edit `config/categories.json`, takes effect live)

- `interrupts.enabled`: `false` switches every pause screen off.
- `pause_seconds`: the countdown. 10 by default.
- `grace_minutes` / `extension_minutes`: what "Go in" and "more" buy you.
- Per category under `limits`: `pause_on_open`, `session_minutes`,
  `daily_minutes`, `block_after_daily` (hard mode: once over budget, only
  Done is offered).
- Add a new thing to watch: new entry under `categories` with `domains`
  and/or `apps`; add `limits` if you want it interrupted.

Meetings, screen shares:

```bash
python3 -m timetrack snooze 90
```

## 4. Morning digest

At 8am a macOS notification summarises yesterday: minutes and opens for X and
YouTube, plus how many times you bounced versus went in. If you never see it,
macOS may be hiding notifications from "osascript" or "Script Editor": check
System Settings > Notifications.

## 5. Reading the week

Dashboard, top to bottom: tiles (today, with budget bars), last 7 days (bar
height is minutes, number on top is opens), by hour, pause screens, everything,
sessions. Use ‹ › to move between days. The CLI version:

```bash
python3 -m timetrack report --sessions
python3 -m timetrack decisions
```

## 6. If something is wrong

Logs in `~/Library/Logs/TimeTrack/`. Restart everything with `./install.sh`.
Remove everything with `./install.sh uninstall`. Data is never deleted by
either; it lives in `~/Library/Application Support/TimeTrack/timetrack.db`.

Known limits, by design:
- Collector polls every 3 seconds, so sub-3-second visits are missed and
  timings are ±3 seconds.
- Watching YouTube with no input counts for up to 60 minutes, then it assumes
  you've walked away. Any other site stops counting after 3 minutes idle.
- An open with no close from the phone is capped at 30 minutes.
- Phone Safari visits to x.com are not seen, only the apps.
