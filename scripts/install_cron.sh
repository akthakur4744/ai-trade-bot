#!/usr/bin/env bash
# Install a launchd agent that runs kite_auto_login.py at 08:55 IST, Mon-Fri.
#
# 08:55 IST = 03:25 UTC. launchd times are local-clock based, so we use local
# time here. Adjust HOUR/MINUTE below if your Mac is not on IST.
#
# Usage:
#   ./scripts/install_cron.sh            # install + load
#   ./scripts/install_cron.sh uninstall  # unload + remove

set -euo pipefail

LABEL="com.insightalpha.kiteauth"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/.insight_alpha"
LOG_FILE="$LOG_DIR/auto_login.log"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$(command -v python3)"

# Trigger time — local clock. Default 08:55 (assumes Mac timezone = IST).
HOUR=8
MINUTE=55

if [[ "${1:-}" == "uninstall" ]]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Uninstalled $LABEL"
  exit 0
fi

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$PLIST")"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${REPO_ROOT}/scripts/kite_auto_login.py</string>
  </array>
  <key>WorkingDirectory</key><string>${REPO_ROOT}</string>
  <key>StandardOutPath</key><string>${LOG_FILE}</string>
  <key>StandardErrorPath</key><string>${LOG_FILE}</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>${HOUR}</integer><key>Minute</key><integer>${MINUTE}</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>${HOUR}</integer><key>Minute</key><integer>${MINUTE}</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>${HOUR}</integer><key>Minute</key><integer>${MINUTE}</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>${HOUR}</integer><key>Minute</key><integer>${MINUTE}</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>${HOUR}</integer><key>Minute</key><integer>${MINUTE}</integer></dict>
  </array>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed $LABEL -> runs at ${HOUR}:${MINUTE} local time Mon-Fri"
echo "Logs: $LOG_FILE"
echo "Dry-run now: launchctl start $LABEL"
