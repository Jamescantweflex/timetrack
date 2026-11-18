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

## Left to the builder

- Exact dashboard layout, as long as today's X and YouTube minutes and opens
  are visible without scrolling.
- Phase 2 design (interrupt mechanics) happens after a baseline week.
