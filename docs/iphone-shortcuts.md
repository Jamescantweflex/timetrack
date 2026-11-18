# iPhone setup (about 10 minutes, on the phone)

iOS won't let an app read Screen Time, so the phone side is Shortcuts
automations that fire when an app opens or closes and append one line to a file
in iCloud Drive. The Mac reads that file.

The file lands at `iCloud Drive / Shortcuts / TimeTrack / phone_events.jsonl`.
The Mac side already watches that path and the folder already exists.

## Part 1: one shortcut that does the writing

Open **Shortcuts** → **Shortcuts** tab → **+**. Name it exactly **TimeTrack Log**.
Add these actions in order (search for each by name):

1. **Receive input** — tap the box at the top: set it to receive **Text** from
   **Nowhere** (this appears when you tap "Shortcut Input" settings; if you
   don't see it, skip, it still works).
2. **Split Text** — Split *Shortcut Input* by **Custom**, separator: a single
   space ` `.
3. **Format Date** — Date: **Current Date**. Date Format: **Custom**. Format
   string (copy exactly):
   `yyyy-MM-dd'T'HH:mm:ssxxx`
4. **Text** — type this, inserting the variables where shown (tap the variable
   chips above the keyboard; for the Split Text items, choose *Split Text* then
   tap it and pick **Item 1**, then again for **Item 2**):

   ```
   {"ts":"[Formatted Date]","app":"[Split Text Item 1]","event":"[Split Text Item 2]"}
   ```

   It must stay on one line with the quotes as written.
5. **Append to Text File** — tap **File Path**, choose **iCloud Drive**, path:
   `TimeTrack/phone_events.jsonl`. Turn **Make New Line** ON. Text: the *Text*
   from step 4.

Test: tap ▶. It will complain there's no input; that's fine. Instead, add a
temporary **Text** action at the very top containing `YouTube open`, run it,
then delete that action. Within a minute the Mac should see one line:
`python3 -m timetrack status` will say the phone file exists.

## Part 2: four automations (two per app)

**Automation** tab → **+** → **App**.

For **YouTube**:
- Choose App: YouTube. Tick **Is Opened**. Tick **Run Immediately** (not "Run
  After Confirmation"). Turn **Notify When Run** OFF. Next.
- **New Blank Automation** → add **Text** with `YouTube open` → add **Run
  Shortcut** → pick **TimeTrack Log**, Input: the *Text*. Done.
- Repeat with **Is Closed** ticked and the text `YouTube close`.

For **X**: the same two automations, with the app X and the texts `X open`
and `X close`.

That's it. Any other app later: two more automations with its name. Then add
the same name under `phone_apps` in `config/categories.json` on the Mac (or
leave it; it shows under its own name anyway).

## Part 3: the phone-side pause (optional, recommended)

The Mac pause screen can't appear on the phone, but the same automation can
make you stop and say why before the feed gets you. In each **Is Opened**
automation, add these two actions **before** the Run Shortcut action:

1. **Ask for Input** — Prompt: `What are you here for?`, Input Type: Text.
   (The feed is already loading underneath; this is the pause.)
2. Leave the rest as is. If you want the intention logged, change the Text
   action to `YouTube open` followed by a space and the *Provided Input*
   variable; the Mac ignores anything after the second word for now.

For a hard stop, use the thing Apple already built: **Settings → Screen Time →
App Limits → Add Limit**: X 30 min, YouTube 45 min, and turn on **Block at End
of Limit**. Those limits match the Mac defaults in `config/categories.json`.

## Known limits

- "Closed" fires when you leave the app, including switching to another app or
  locking the phone. Good enough.
- If a close is missed, the Mac caps that session at 30 minutes.
- Safari visits to x.com on the phone are not caught. Use the apps.
- iCloud sync can lag a few minutes when the phone is on cellular.
