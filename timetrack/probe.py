"""Trigger every macOS permission prompt the agents will ever need, in one go.
Run under launchd so the prompts are attributed to the same python3 the agent uses."""
import subprocess, sys, time
from .collector import CHROMIUM_SCRIPT, SAFARI_SCRIPT, WINDOW_TITLE_SCRIPT, FRONT_APP_SCRIPT, installed_browsers

def run(name, script):
    t0 = time.time()
    try:
        out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
        ok = out.returncode == 0
        msg = (out.stdout.strip() or out.stderr.strip())[:100]
    except subprocess.TimeoutExpired:
        ok, msg = False, "timed out (dialog not answered)"
    print(f"{'OK ' if ok else 'NO '} {name:<28} {time.time()-t0:5.1f}s  {msg}", flush=True)

run("System Events (frontmost app)", FRONT_APP_SCRIPT)
run("Accessibility (window title)", WINDOW_TITLE_SCRIPT)
browsers = installed_browsers()
print("browsers found: " + (", ".join(browsers) or "none"), flush=True)
for app in browsers:
    run(f"Automation: {app}", SAFARI_SCRIPT if app == "Safari" else CHROMIUM_SCRIPT % app)
print("done", flush=True)
