# iPhone setup (about 10 minutes, on the phone)

Apple doesn't let any app read Screen Time, so the phone side is the built-in
**Shortcuts** app: an automation fires when you open or close an app, asks
"Productive, or wasting time?", and writes one line to a file in iCloud Drive
that the Mac reads. You need iCloud Drive on, with the same Apple ID on the
phone and the Mac.

## Part 1: the logging shortcut (once)

Shortcuts app → **Shortcuts** tab → **+** → tap the name at the top → rename
to exactly **TimeTrack Log**. Add three actions (search each by name):

1. **Format Date**. Leave the date as *Current Date*. Tap the format and
   choose **ISO 8601**, then expand the action (the little arrow) and turn on
   **Include ISO 8601 Time**.
2. **Text**. Type this on one line, and where it says [...] insert the
   variable from the bar above the keyboard instead of typing:

   ```
   {"ts":"[Formatted Date]","e":"[Shortcut Input]"}
   ```

3. **Append to Text File**. File path: `TimeTrack/phone_events.jsonl`, in the
   **Shortcuts** folder of iCloud Drive (the default). **Make New Line** on.

Tap Done.

## Part 2: automations, two per app

**Automation** tab → **+** → **App**.

**When you open the app** (the pause):

- Choose the app (say YouTube). Tick **Is Opened** only. Choose **Run
  Immediately**. Next → **New Blank Automation**.
- Add **Choose from Menu**. Prompt: `Productive, or wasting time?`. Rename the
  two options to **Wasting time** and **Productive**.
- Under **Wasting time**, add **Go to Home Screen**.
- Below **End Menu**, add **Text** containing `YouTube open`, then **Run
  Shortcut** → *TimeTrack Log*, and set its input to that Text. Done.

**When you leave the app** (the stopwatch):

- **+** → **App** → same app, tick **Is Closed** only, **Run Immediately**.
- **Text** containing `YouTube close` → **Run Shortcut** → *TimeTrack Log*
  with that Text as input. Done.

Repeat both for each app you want watched (X: `X open` and `X close`). The
first word(s) must match the name under **iPhone apps** for that category in
the dashboard's Watch list. "Wasting time" still logs a short visit, which is
what you want to see.

## Part 3: check it reached the Mac

Open and close YouTube once on the phone, wait a minute, then on the Mac:

```
python3 -m timetrack status
```

should say the phone file exists, and the YouTube tile on the dashboard shows
phone minutes. iCloud can take a few minutes on mobile data.

## Hard stop (optional)

**Settings → Screen Time → App Limits → Add Limit**, with **Block at End of
Limit** on. That is Apple's own block and the only real one on a phone.

## Known limits

- "Closed" fires when you leave the app, including locking the phone.
- A missed close is capped at 30 minutes.
- Websites in Safari on the phone are not caught. Use the apps, or add Safari
  itself as a watched app.
- If Format Date has no ISO 8601 option on your iOS version, choose **Custom**
  and enter `yyyy-MM-dd'T'HH:mm:ssxxx`.
