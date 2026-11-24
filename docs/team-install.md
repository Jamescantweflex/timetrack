# TimeTrack: install on your Mac (10 minutes)

TimeTrack shows you where your screen time goes and, for sites you choose,
puts up a full-screen "Productive, or wasting time?" question when you open
them. Everything stays on your Mac. Nothing is uploaded anywhere.

## 1. Install Python

Download the macOS installer from https://www.python.org/downloads/macos/
(the "macOS 64-bit universal2 installer" for the latest 3.x) and run it.
The Mac's built-in Python is too old, so this step is required.

## 2. Put the TimeTrack folder in your home folder

Unzip `timetrack.zip` and move the `timetrack` folder to your home folder
(the one with your name, next to Desktop and Documents). Don't leave it in
Downloads: if the folder moves later, the trackers stop.

## 3. Install the background agents

Open Terminal (Spotlight: type "Terminal"), then paste these two lines one
at a time and press Return after each:

```
cd ~/timetrack
zsh install.sh
```

You should see three "started" lines and a dashboard address.

## 4. Grant permissions

Paste this and press Return:

```
python3 -m timetrack probe
```

macOS will show several permission dialogs: letting Python control
"System Events", your browser (Chrome, Arc, Safari), and Accessibility.
Click **Allow** or **OK** on each. If Accessibility opens System Settings,
switch on **python3** in the list, then re-run the command above until every
line says OK.

## 5. Open the dashboard and make it yours

http://127.0.0.1:8765. That address means "this Mac": nobody else can open
it, and on your colleague's Mac it shows their data, not yours.

The page opens with a **Make it yours** note. Scroll to **Watch list and
settings** and set two things:

1. **What you drift onto.** Add the sites and apps you want the pause screen
   for (your equivalent of X and YouTube), and remove the ones that aren't
   yours. Or click **Watch** next to anything in the day's list.
2. **What you should be doing instead.** Fill in "Instead of drifting, I
   should: ...", for example "Call a client", "Go for a walk", "Meditate".
   It shows on every pause screen, and once a day, before the screen lets you
   through as "productive", it asks whether you've done it yet.

Click **Save**. The trackers pick it up within seconds.

## 6. Put it in the Dock as an app

In **Safari**, open http://127.0.0.1:8765 and choose **File > Add to Dock**.
TimeTrack then has its own icon and window, no address bar or tabs, and it
behaves like any other app. (Chrome: menu > Cast, save and share > Install
page as app. Arc can't do this; use Safari for this one step.)

## Everyday

- The pause screen: **Esc** = wasting time, closes the tab and sends you to
  the dashboard. **Return** = productive, buys 10 minutes, then asks again.
  No answer for 60 seconds counts as wasting time.
- Turn it off for a while: in Terminal, `cd ~/timetrack` then
  `python3 -m timetrack snooze 90` (minutes).
- Remove it completely: `cd ~/timetrack` then `zsh install.sh uninstall`.

## iPhone (optional)

See `docs/iphone-shortcuts.md`. Apple doesn't let apps read Screen Time, so
the phone side is a Shortcuts automation you set up once.
