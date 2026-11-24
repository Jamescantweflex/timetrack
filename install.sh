#!/bin/zsh
# Install (or reinstall) TimeTrack's launchd agents for the current user, on any Mac.
# Usage: ./install.sh            install/restart all four agents
#        ./install.sh uninstall  stop and remove them (data is kept)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/TimeTrack"
mkdir -p "$AGENTS" "$LOGS"
PY="$(command -v python3)"
if ! "$PY" -c "import sys; assert sys.version_info >= (3, 10); import tkinter, sqlite3" 2>/dev/null; then
  echo "Need Python 3.10+ with tkinter. Install from https://www.python.org/downloads/macos/ and re-run." >&2
  exit 1
fi
LABEL_PREFIX="com.timetrack.$(id -un)"

write_plist() {   # name, args..., writes $AGENTS/$label.plist
  local name="$1"; shift
  local label="$LABEL_PREFIX.$name"
  local prog="$PY"
  [[ "$name" == "menubar" ]] && prog="/usr/bin/osascript"
  local args=""; for a in "$@"; do args+="    <string>$a</string>\n"; done
  local extra=""
  [[ "$name" == "interrupter" || "$name" == "menubar" ]] && extra="  <key>ProcessType</key><string>Interactive</string>\n  <key>EnvironmentVariables</key><dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>\n"
  printf '%b' "<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>
    <string>$prog</string>
$args  </array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
$extra  <key>StandardOutPath</key><string>$LOGS/$name.log</string>
  <key>StandardErrorPath</key><string>$LOGS/$name.log</string>
</dict></plist>
" > "$AGENTS/$label.plist"
}

for name in collector dashboard interrupter menubar; do
  label="$LABEL_PREFIX.$name"
  launchctl bootout "gui/$UID/$label" 2>/dev/null || true
  if [[ "${1:-}" == "uninstall" ]]; then rm -f "$AGENTS/$label.plist"; echo "removed $label"; continue; fi
  case $name in
    collector)   write_plist collector -m timetrack collect ;;
    dashboard)   write_plist dashboard -m timetrack serve --port 8765 ;;
    interrupter) write_plist interrupter -m timetrack interrupt ;;
    menubar)     write_plist menubar -l JavaScript "$HERE/timetrack/menubar.js" ;;
  esac
  ok=0
  for try in 1 2 3 4 5 6; do
    if launchctl bootstrap "gui/$UID" "$AGENTS/$label.plist" 2>/dev/null; then ok=1; break; fi
    sleep 1
  done
  [[ $ok == 1 ]] && echo "started $label" || echo "FAILED to start $label (see $LOGS/$name.log)"
done

if [[ "${1:-}" != "uninstall" ]]; then
  sleep 2
  for name in collector dashboard interrupter menubar; do
    printf "%-12s " "$name"; launchctl print "gui/$UID/$LABEL_PREFIX.$name" 2>/dev/null | grep -E "^\s+pid = " | head -1 || echo "not running"
  done
  echo
  echo "Dashboard: http://127.0.0.1:8765"
  echo "First run: macOS will ask to let python3 control System Events and each browser you have installed. Click Allow each time."
  echo "To trigger all those prompts now:  $PY -m timetrack probe"
fi
