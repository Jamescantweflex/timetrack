#!/bin/zsh
# Install (or reinstall) the launchd agents so TimeTrack runs at login.
# Usage: ./install.sh            install/restart all three
#        ./install.sh uninstall  stop and remove
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$HOME/Library/Logs/TimeTrack"

for name in collector dashboard interrupter; do
  label="com.timetrack.legacy.$name"
  launchctl bootout "gui/$UID/$label" 2>/dev/null || true
  if [[ "${1:-}" == "uninstall" ]]; then
    rm -f "$AGENTS/$label.plist"; echo "removed $label"; continue
  fi
  cp "$HERE/launchd/$label.plist" "$AGENTS/$label.plist"
  ok=0
  for try in 1 2 3 4 5 6; do          # launchd needs a beat after bootout
    if launchctl bootstrap "gui/$UID" "$AGENTS/$label.plist" 2>/dev/null; then ok=1; break; fi
    sleep 1
  done
  if [[ $ok == 1 ]]; then echo "started $label"; else echo "FAILED to start $label"; fi
done

if [[ "${1:-}" != "uninstall" ]]; then
  sleep 2
  for name in collector dashboard interrupter; do
    printf "%-12s " "$name"; launchctl print "gui/$UID/com.timetrack.legacy.$name" 2>/dev/null | grep -E "^\s+pid = " | head -1 || echo "not running"
  done
  echo "dashboard: http://127.0.0.1:8765"
fi
