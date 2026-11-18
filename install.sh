#!/bin/zsh
# Install (or reinstall) the two launchd agents so TimeTrack runs at login.
# Usage: ./install.sh            install/restart
#        ./install.sh uninstall  stop and remove
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$HOME/Library/Logs/TimeTrack"

for name in collector dashboard; do
  label="com.timetrack.legacy.$name"
  if [[ "${1:-}" == "uninstall" ]]; then
    launchctl bootout "gui/$UID/$label" 2>/dev/null || true
    rm -f "$AGENTS/$label.plist"
    echo "removed $label"
    continue
  fi
  launchctl bootout "gui/$UID/$label" 2>/dev/null || true
  cp "$HERE/launchd/$label.plist" "$AGENTS/$label.plist"
  launchctl bootstrap "gui/$UID" "$AGENTS/$label.plist"
  echo "started $label"
done

if [[ "${1:-}" != "uninstall" ]]; then
  sleep 2
  launchctl print "gui/$UID/com.timetrack.legacy.collector" | grep -E "state|pid" | head -2
  echo "dashboard: http://127.0.0.1:8765"
fi
