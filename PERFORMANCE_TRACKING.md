# Performance Tracking Guide

## Overview

The `performance_tracker.py` script automatically updates token performance data by:
- Fetching current prices from Birdeye
- Tracking price changes at 1h, 24h, 7d, and 30d intervals
- Detecting rug pulls (liquidity drops or 99%+ price crashes)
- Calculating max gains and losses
- Updating source performance statistics

## Manual Usage

### Update All Tokens
```bash
python3 performance_tracker.py
```

### Update Only Recent Tokens (limit to 10)
```bash
python3 performance_tracker.py --limit 10
```

### Update Only Tokens Older Than 24 Hours
```bash
python3 performance_tracker.py --min-age 24
```

### Show Summary Only (No Updates)
```bash
python3 performance_tracker.py --summary
```

## Automated Tracking with Cron

### Option 1: Update Every Hour
```bash
# Edit crontab
crontab -e

# Add this line (replace path with your actual path):
0 * * * * cd /path/to/sweetmemerep && /usr/bin/python3 performance_tracker.py >> performance_tracker.log 2>&1
```

### Option 2: Update Every 6 Hours
```bash
0 */6 * * * cd /path/to/sweetmemerep && /usr/bin/python3 performance_tracker.py >> performance_tracker.log 2>&1
```

### Option 3: Update Daily at 9 AM
```bash
0 9 * * * cd /path/to/sweetmemerep && /usr/bin/python3 performance_tracker.py >> performance_tracker.log 2>&1
```

## macOS Launchd (Alternative to Cron)

Create file: `~/Library/LaunchAgents/com.memecoin.tracker.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memecoin.tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/sweetmemerep/performance_tracker.py</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer> <!-- Run every hour (3600 seconds) -->
    <key>StandardOutPath</key>
    <string>/path/to/sweetmemerep/tracker.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/sweetmemerep/tracker_error.log</string>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.memecoin.tracker.plist
```

## What Gets Tracked

### Time-Based Price Tracking
- **1 hour later**: First price check after 1+ hour
- **24 hours later**: First price check after 24+ hours
- **7 days later**: First price check after 7+ days
- **30 days later**: First price check after 30+ days

### Performance Metrics
- **Max Gain Observed**: Highest % gain ever recorded
- **Max Loss Observed**: Lowest % loss ever recorded
- **Token Still Alive**: Yes/No based on API availability
- **Rug Pull Occurred**: Auto-detected via liquidity drop or 99%+ crash

### Rug Pull Detection
Automatically marks as rug pull if:
- Liquidity drops below $1,000
- Price crashes 99%+ from entry

## Example Output

```
============================================================
📊 PERFORMANCE TRACKER
============================================================

📋 Found 5 token(s) to update

[1/5] BONK from Alpha Group #3
  Checking DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263...
  📊 Current: $0.0000105300 (+2.50%)
  ✅ Performance updated

[2/5] PEPE from Discord Degens
  Checking 4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R...
  🚨 RUG PULL DETECTED - Liquidity: $450.00
  ✅ Performance updated

[3/5] WIF from Elite Signals
  Checking EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm...
  📊 Current: $0.0003425000 (+485.20%)
  ✅ Performance updated

📈 Updating source statistics...
  ✅ Updated Alpha Group #3
  ✅ Updated Discord Degens
  ✅ Updated Elite Signals

============================================================
✅ Performance tracking complete!
============================================================

📊 TRACKING SUMMARY
────────────────────────────────────────────────────────────
Total Tracked: 5
Still Alive: 4
Rug Pulls: 1
Avg Max Gain: 97.43%
Best Gain: 485.20%
Worst Loss: -99.50%
```

## Behavior

- The tracker records time-series snapshots for active WATCH and TRADE positions.
- Data collection stops when a token is removed from WATCH or a trade is exited.
- Each run appends a row to `performance_history` and updates summary fields in `performance_tracking`.

## Notes

- The tracker only runs on active WATCH or TRADE positions.
