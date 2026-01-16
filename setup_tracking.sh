#!/bin/bash
# Setup script for automatic hourly performance tracking

echo "🔧 Memecoin Analyzer - Performance Tracking Setup"
echo "=================================================="
echo ""

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_PATH=$(which python3)

echo "Installation directory: $SCRIPT_DIR"
echo "Python path: $PYTHON_PATH"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "Detected: macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "Detected: Linux"
else
    echo "⚠️  Unsupported OS: $OSTYPE"
    echo "Please manually configure cron or task scheduler"
    exit 1
fi

echo ""
echo "This will set up automatic performance tracking EVERY 15 MINUTES."
echo "The tracker will run every 15 minutes in the background and update"
echo "token prices, detect rug pulls, and refresh source statistics."
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

if [[ "$OS" == "macos" ]]; then
    # macOS - use launchd
    echo ""
    echo "Setting up macOS LaunchAgent..."

    PLIST_FILE="$HOME/Library/LaunchAgents/com.memecoin.tracker.plist"
    LOG_FILE="$SCRIPT_DIR/performance_tracker.log"
    ERROR_LOG_FILE="$SCRIPT_DIR/performance_tracker_error.log"

    # Create the plist file
    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memecoin.tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>$SCRIPT_DIR/performance_tracker.py</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$ERROR_LOG_FILE</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

    # Set permissions
    chmod 644 "$PLIST_FILE"

    # Load the agent
    launchctl unload "$PLIST_FILE" 2>/dev/null  # Unload if already exists
    launchctl load "$PLIST_FILE"

    echo "✅ LaunchAgent installed and loaded!"
    echo ""
    echo "📋 Configuration:"
    echo "   Runs every: 15 minutes"
    echo "   Log file: $LOG_FILE"
    echo "   Error log: $ERROR_LOG_FILE"
    echo ""
    echo "🔧 Management commands:"
    echo "   Stop:  launchctl unload $PLIST_FILE"
    echo "   Start: launchctl load $PLIST_FILE"
    echo "   View logs: tail -f $LOG_FILE"

elif [[ "$OS" == "linux" ]]; then
    # Linux - use cron
    echo ""
    echo "Setting up cron job..."

    CRON_CMD="*/15 * * * * cd $SCRIPT_DIR && $PYTHON_PATH performance_tracker.py >> $SCRIPT_DIR/performance_tracker.log 2>&1"

    # Check if cron job already exists
    (crontab -l 2>/dev/null | grep -v "performance_tracker.py"; echo "$CRON_CMD") | crontab -

    echo "✅ Cron job installed!"
    echo ""
    echo "📋 Configuration:"
    echo "   Runs every: 15 minutes"
    echo "   Command: $CRON_CMD"
    echo ""
    echo "🔧 Management commands:"
    echo "   View cron jobs: crontab -l"
    echo "   Edit cron jobs: crontab -e"
    echo "   View logs: tail -f $SCRIPT_DIR/performance_tracker.log"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SETUP COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 The performance tracker will now run automatically every 15 minutes."
echo ""
echo "📊 Next steps:"
echo "   1. Analyze tokens using: python3 analyzer.py"
echo "   2. Wait for 15-min update (or run manually: python3 performance_tracker.py)"
echo "   3. View updated source stats in analyzer.py option [2]"
echo ""
echo "💡 Tip: The first run happens in 15 minutes, or run manually now to test:"
echo "   python3 performance_tracker.py"
echo ""
