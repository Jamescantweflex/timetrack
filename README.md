# TimeTrack

Where does my tech time go. Local only. Mac collector + iPhone Shortcuts events
→ SQLite → a dashboard at http://127.0.0.1:8765.

Design: `docs/design.md`. iPhone setup: `docs/iphone-shortcuts.md`.
What to test: `docs/testing-guide.md`.

Three background agents: **collector** (what's in front, every 3 s),
**interrupter** (pause screen on opening X/YouTube, sitting and daily limits,
morning digest), **dashboard** (the web page).

## Run

```bash
./install.sh            # installs three launchd agents, runs at login
python3 -m timetrack status
python3 -m timetrack report --sessions
python3 -m timetrack report --date 2026-11-18
python3 -m timetrack decisions           # pause-screen answers
python3 -m timetrack snooze 90           # no pause screens for 90 min
python3 -m timetrack demo --kind pause   # see the screen with fake numbers
./install.sh uninstall
```

Logs: `~/Library/Logs/TimeTrack/`. Data: `~/Library/Application Support/TimeTrack/timetrack.db`.

## Add something to track

Edit `config/categories.json`. Domains match by suffix, apps by Mac app name,
`phone_apps` by the name used in the iPhone shortcut. `passive: true` means
time with no keyboard/mouse still counts (video). The dashboard re-reads the
file on every request.

## Tests

```bash
python3 tests/test_collector.py
```

## Interrupts

`interrupts` and each category's `limits` in `config/categories.json`. Live
reload. `enabled: false` turns everything off. The engine is pure and tested
(`tests/test_engine.py`); the UI is Tk, full-screen, forced to the front.

```bash
python3 tests/test_engine.py
```
