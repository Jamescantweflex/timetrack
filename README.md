# TimeTrack

Where does my tech time go. Local only. Mac collector + iPhone Shortcuts events
→ SQLite → a dashboard at http://127.0.0.1:8765.

Design: `docs/design.md`. iPhone setup: `docs/iphone-shortcuts.md`.

## Run

```bash
./install.sh            # installs two launchd agents (collector + dashboard), runs at login
python3 -m timetrack status
python3 -m timetrack report --sessions
python3 -m timetrack report --date 2026-11-18
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

## Phase 2 (after a baseline week)

Interrupts: a pause screen on open, nudges after N minutes, Screen Time limits
on the phone. Not built yet, on purpose.
