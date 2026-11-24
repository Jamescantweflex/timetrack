# TimeTrack

Where does your tech time go, and a nudge when it goes somewhere you didn't
choose. TimeTrack runs quietly on a Mac, records which app or website is in
front of you, and shows it on a private dashboard. For the sites you pick
(your equivalent of X and YouTube), it puts up a full-screen question the
moment you open them: **Productive, or wasting time?** It also reminds you
what you said you'd rather be doing instead.

Everything stays on your own Mac. Nothing is uploaded anywhere.

**Install:** download `timetrack.zip` from the
[latest release](https://github.com/Jamescantweflex/timetrack/releases/latest)
and follow [Install](#install) below. About 10 minutes.

---

## How it works

**What it records.** Every 3 seconds a small background program asks macOS
which app is at the front. If that's a browser, it also reads the address of
the active tab, so "Chrome on x.com" and "Chrome on docs.google.com" are
different things. Consecutive readings of the same thing are stitched into one
stretch of time. When you switch windows, a new stretch starts.

**Idle.** If you don't touch the keyboard or mouse for 3 minutes, TimeTrack
assumes you've walked away and stops counting from the moment you went quiet.
Categories marked **Video** (YouTube) or **Calls** (Meet, Zoom, Teams) get a
60-minute allowance instead, because you watch and talk without typing.

**Categories.** Your settings group sites and apps into named categories:
"X" is x.com and twitter.com, "YouTube" is youtube.com and youtu.be, and so
on. The dashboard tiles, charts and budgets work per category. Anything you
haven't categorised still shows in the day's full list at the bottom, with a
**Watch** button to start tracking it.

**Sessions and opens.** Time on a category with gaps under a minute is one
sitting. The number of sittings per day is your "opens", which is usually the
number that surprises people.

**The pause screen.** For a category with the pause screen on, the moment a
new sitting starts a full-screen window appears over everything:

1. A short countdown (10 seconds by default) with today's total so far, and
   your **Instead** line: what you said you'd rather be doing.
2. Two buttons. **Wasting time** (or Esc) closes that tab, sends it to the
   dashboard, and logs the choice. **Being productive** (or Return) lets you
   in for 10 minutes, after which it asks again.
3. Once a day, the first time you say "productive", it asks **Have you done
   this today?** about your Instead action. **No** means that comes first and
   the tab closes. **Yes** lets you through and it won't ask again until
   tomorrow.
4. No answer for 60 seconds counts as wasting time. The screen never just
   disappears.

Per-sitting and per-day budgets, and a "Hard" mode that gives no override
once the daily budget is spent, are optional per category.

**The dashboard** at http://127.0.0.1:8765 shows today's tiles with budget
bars, the last 7 days, time by hour of day, every pause screen and what you
chose, and the full list of where the day went. The **Watch list and
settings** panel at the bottom is where you make it yours.

**The menu-bar icon.** A small hourglass at the top right of the screen shows
today's time on your watched sites. Click it for the breakdown per site
against its budget, your Instead action, a shortcut to the dashboard, and
**Snooze** for 30 minutes, 1 hour or 2 hours when you're presenting or in a
meeting. The icon changes to an exclamation mark when you're over a daily
budget and a moon while snoozed.

**Four background programs** do this: the *collector* (recording), the
*interrupter* (pause screens and the 8am digest notification), the
*dashboard* (the web page) and the *menu bar* icon. They start at login and
restart if they crash.

---

## Install

### 1. Python

Download the macOS installer from https://www.python.org/downloads/macos/
(the "macOS 64-bit universal2 installer" for the latest 3.x) and run it. The
Mac's built-in Python is too old, so this step is required.

### 2. The TimeTrack folder

Download `timetrack.zip` from the
[latest release](https://github.com/Jamescantweflex/timetrack/releases/latest),
unzip it, and move the `timetrack` folder into your home folder (the one with
your name, next to Desktop and Documents). Don't leave it in Downloads: if the
folder moves later, the trackers stop.

### 3. Start it

Open Terminal (press Cmd-Space, type `Terminal`, Return). Paste these two
lines one at a time, pressing Return after each:

```
cd ~/timetrack
zsh install.sh
```

You should see four `started` lines and the dashboard address, and an
hourglass icon appears in the menu bar at the top right of the screen.

### 4. Permissions

Paste this and press Return:

```
python3 -m timetrack probe
```

macOS will show several dialogs asking to let Python control **System
Events**, each browser you have installed (Safari, and Chrome or Arc if present), and **Accessibility**. Click
**Allow** or **OK** on each one. If Accessibility opens System Settings,
switch on **python3** in the list. Run the command again until every line
says `OK`.

This is the step people skip. Without these permissions TimeTrack runs but
records nothing.

### 5. Check it's working

```
python3 -m timetrack status
```

should say `collector: ALIVE`. Then open http://127.0.0.1:8765. Within a
minute the day's list at the bottom starts filling in.

---

## Make it yours

The dashboard opens with a **Make it yours** note until you save settings
once. Scroll to **Watch list and settings**:

1. **What you drift onto.** Edit the categories so they're yours: add the
   sites and apps you want the pause screen for, delete the ones that aren't
   you. Websites are comma-separated domains (`x.com, twitter.com`); Mac apps
   go by their name as it appears in the menu bar. Or click **Watch** next to
   anything in the day's list.
2. **What you should be doing instead.** Fill in *Instead of drifting, I
   should:* with the thing you'd rather be doing: "Call a client", "Go for a
   walk", "Meditate". It shows on every pause screen, and once a day the
   screen checks whether you've done it before letting you through as
   productive. You can override it per category in the **Instead** column.
3. Adjust the countdown, how long "productive" buys, and budgets if you want.

Click **Save**. The background programs pick up changes within seconds.

---

## Put it in the Dock as an app

The dashboard is a web page served by your own Mac, but you can give it an
icon and its own window with no address bar or tabs:

- **Safari** (macOS Sonoma or later): open http://127.0.0.1:8765, then
  **File > Add to Dock**. Apple documents this at
  https://support.apple.com/en-au/104996.
- **Chrome:** open the page, then the **⋮** menu > **Cast, save, and share** >
  **Install page as app**. The app lands in Applications > Chrome Apps;
  right-click its Dock icon > Options > Keep in Dock.
- **Arc** can't do this. Arc's help centre says it does not support installing
  web apps and suggests pinning the page as a Favorite instead
  (https://resources.arc.net/hc/en-us/articles/25678978728983). TimeTrack
  still tracks Arc perfectly well; this only affects how you *view* the
  dashboard. Use Safari for this one step, or just bookmark the address in
  Arc.

Why 127.0.0.1? It's the address every computer uses to mean "this machine".
Only you can open it, and on a colleague's Mac the same address shows their
data, not yours.

---

## Everyday use

- **Esc** = wasting time. **Return** = productive. The hint at the bottom of
  the screen repeats this.
- **Snooze** pause screens for a while: click the menu-bar hourglass and pick
  a length. (Terminal equivalent: `python3 -m timetrack snooze 90`.)
- **Turn pause screens off** entirely: untick *Pause screens on* in settings.
- **Report in Terminal:** `python3 -m timetrack report --sessions`.
- **Morning digest:** an 8am notification with yesterday's totals.
- **Uninstall:** `cd ~/timetrack` then `zsh install.sh uninstall`. Your data
  file is kept; delete `~/Library/Application Support/TimeTrack` to remove it.

## Updating

Download the new `timetrack.zip` from the releases page, unzip it, replace
your `~/timetrack` folder with the new one, then run `cd ~/timetrack` and
`zsh install.sh` again. Your data and settings live outside the folder and
are kept. (Your settings are in `config/categories.json` inside the folder,
so copy that file across first if you've customised it.)

---

## If something's wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard shows nothing, `status` says collector ALIVE | A permission wasn't granted | Run `python3 -m timetrack probe` again; every line must say OK |
| Pause screen never appears | Site isn't in a category with *Pause screen* ticked; or you answered "productive" in the last 10 minutes; or snoozed | Check settings; `python3 -m timetrack status` shows snooze |
| Pause screen appears for the wrong thing | Domain matches by suffix | Narrow the domain in settings |
| Menu-bar icon shows `–` or is missing | Dashboard program isn't running, or the menu bar is full and macOS has hidden it | `cd ~/timetrack` then `zsh install.sh`; quit a few other menu-bar apps |
| Dashboard page won't load | Programs aren't running | `cd ~/timetrack` then `zsh install.sh` |
| "Need Python 3.10+ with tkinter" | Built-in Python | Install from python.org (step 1) |
| A long call shows as a few minutes | Idle rule | Add the app or site to the **Calls** category |

Logs: `~/Library/Logs/TimeTrack/`. Data: `~/Library/Application
Support/TimeTrack/timetrack.db`.

---

## Privacy and security

- Everything is on your Mac: the recording, the database, the dashboard. No
  account, no server, no network traffic.
- What's recorded: app name, website domain, window title, start and end
  time. Window titles can include things like email subjects, so treat the
  data file as private.
- The dashboard only answers requests from your own machine addressed to
  127.0.0.1 or localhost, and only from its own page, so a web page you visit
  can't read or change your data.
- The permissions you grant (controlling System Events and your browser,
  Accessibility) are what let it see the front window and close a tab. Grant
  them to the Python you installed, nothing else.

## Browsers

Tracked by site: **Safari, Google Chrome, Arc**, plus Brave and Edge. Firefox
and Firefox-based browsers (Zen, LibreWolf, ...) don't let anything read the
current tab, so time there is recorded as "Firefox" without the site, and the
dashboard status line says so. Use one of the tracked browsers for the sites
you want the pause screen on.

## iPhone (optional)

Apple doesn't let apps read Screen Time, so the phone side is a Shortcuts
automation that logs when you open chosen apps. See
[docs/iphone-shortcuts.md](docs/iphone-shortcuts.md).

---

## For developers

Python 3.10+, standard library only (sqlite3, tkinter, http.server,
osascript). `timetrack/collector.py` records, `timetrack/engine.py` is the
pure interrupt state machine, `timetrack/interrupter.py` is the Tk pause
screen, `timetrack/dashboard.py` + `dashboard.html` the web page,
`timetrack/menubar.js` the menu-bar item (JavaScript for Automation, drawing
what `menubar.py` computes),
`timetrack/rules.py` the config. Design notes in
[docs/design.md](docs/design.md).

```bash
python3 tests/test_engine.py
python3 tests/test_collector.py
python3 tests/test_dashboard.py
python3 tests/test_menubar.py
python3 -m timetrack demo --kind pause   # the screen with fake numbers
```
