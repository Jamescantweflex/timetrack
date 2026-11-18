# TimeTrack — design (short)

Date: 2026-11-19. Owner: James Cant. Status: approved in conversation ("sounds good. lets build").

## Intent

James loses time to X and YouTube without noticing he has started. The tool
makes the unconscious visible first, then interrupts it. It is one part of a
broader effort to break the habit, not the whole fix.

## Goals

- Log where tech time goes on the Mac (every app, every browser domain), and
  on the iPhone for chosen apps.
- Answer "how much X / YouTube today, this week, when, how many opens" with a
  local dashboard.
- Grow to any "where did my time go" question by adding categories, not code.
- Phase 2: interrupt at the moment of opening (pause screen) and after limits.

## Non-goals

- Cloud sync, accounts, sharing. Everything is local to James's Mac plus a
  file in his own iCloud Drive.
- Capturing iPhone usage for apps James hasn't opted in. iOS does not allow it
  (Apple's DeviceActivity framework keeps Screen Time data inside a sandboxed
  report extension; it cannot be exported. Apple-documented, verify against
  current docs before relying on it).
- Replacing Screen Time's hard blocks. Phase 2 uses them rather than fighting
  them.

## Anti-goals

- A tracker that quietly stops logging (sleep, lock, crash) and shows a
  flattering number. Gaps must be honest.
- A nudge so noisy it gets switched off in a week.

## Approaches considered

1. **ActivityWatch as the Mac collector**, our rules and dashboard on top.
   Fastest to real data, but URL capture needs a browser extension and its
   data model would not match the phone events. Rejected for now; can be
   imported later.
2. **Own Python collector** (chosen). ~150 lines, AppleScript for the
   frontmost app and Arc/Chrome/Safari tab URL, `ioreg` for idle time, SQLite
   for storage. One schema for Mac and phone. No dependencies beyond Python.
3. **Native Swift menu-bar app.** Nicer, but slower to build and not needed
   until Phase 2 interrupts.

## Decided

- **Capture everything, decide later.** The collector records spans of
  (app, domain, title). Categories are applied at query time from
  `config/categories.json`. Adding a thing to watch = adding a pattern.
- **Spans, not samples.** The collector keeps one open span and heartbeats
  its end time, so a crash loses at most one poll interval.
- **Idle handling.** Input idle over 3 minutes closes the span, except for
  categories marked `passive` (video) where the limit is 60 minutes.
  Screen lock closes the span immediately.
- **Phone events via iCloud Drive.** Shortcuts automations append one JSON
  line per open/close to `iCloud Drive/TimeTrack/phone_events.jsonl`. The
  Mac ingests it. No server, works off-network, syncs when it can.
- **Sessions.** A session is consecutive spans of one category with gaps
  under 60 seconds. Opens per day is a first-class number.
- **Storage.** `~/Library/Application Support/TimeTrack/timetrack.db`,
  outside iCloud so sync never touches a live SQLite file.
- **Dashboard.** Python stdlib HTTP server on 127.0.0.1:8765, one HTML page.
- **Runs at login** via two launchd agents (collector, dashboard).

## Phase 2, built the same day

James left for a few days with "make your own decisions, give me something to
test". So the baseline-week-first plan was collapsed: interrupts are built and
switched on with default thresholds, to be tuned against the data.

- **Interrupt at the entry.** A full-screen pause screen when a session of X
  or YouTube starts: what you're here for, 10-second countdown, then "Go in"
  (10 min allowance) or "Not now" (tab is sent to the dashboard). Grounded in
  the one sec field study (Grüning et al., PNAS 2023; numbers unverified).
- **Then limits.** Per sitting (X 10 min, YouTube 20) and per day (30 / 45).
  Over the sitting: "5 more minutes" or "Done". Over the day: the screen says
  so; "Override" stays available unless `block_after_daily` is on.
- **Nothing silent.** Every screen and every answer is logged (decisions
  table) and shown on the dashboard. Bounces are the metric of success.
- **Separate agent.** The interrupter reads the collector's spans; it never
  slows capture. Pure state machine (`engine.py`) with tests; Tk for the UI.
- **Escape hatches.** `enabled: false`, `snooze N`, and the window closes on
  its own if you've left the category for a minute.
- **Phone.** Shortcuts "Ask for Input" as the pause, Screen Time app limits
  as the hard stop. No custom app; iOS allows nothing better.

Defaults are my calls (Assumption): 10 s pause, 10 min grace, 5 min extension,
X 10/30, YouTube 20/45. Revisit after a week of data.

## Left to the builder

- Exact dashboard layout, as long as today's X and YouTube minutes and opens
  are visible without scrolling.
- Tuning the interrupt thresholds once there is a week of real data.
