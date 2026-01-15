# 🪙 Memecoin Trading Analyzer

A comprehensive CLI tool for analyzing memecoin trading opportunities on Solana and BNB Chain. Track calls, analyze safety metrics, record decisions, and measure source performance over time.

## Features

- **Real-time Analysis**: Fetch live data from DexScreener and RugCheck APIs
- **Safety Scoring**: Automated safety score (0-10) based on multiple risk factors
- **Red Flag Detection**: Automatic detection of critical risks (low liquidity, mint authority, whale concentration)
- **Decision Tracking**: Record your trading decisions with notes and emotional state
- **Source Performance**: Track which sources provide the best calls over time
- **Performance Tracking**: Automated script to track token prices over time (1h, 24h, 7d, 30d)
- **Rug Pull Detection**: Automatic detection of rugged tokens via liquidity drops
- **SQLite Database**: All data saved locally for historical analysis
- **No API Keys Required**: Uses free public APIs

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd sweetmemerep
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. **Set up automatic hourly tracking** (recommended):
```bash
./setup_tracking.sh
```

This sets up automatic performance tracking every hour so your source stats are always up-to-date. The tracker runs in the background via cron (Linux) or launchd (macOS).

That's it! No API keys needed.

## Quick Start

Run the analyzer:
```bash
python3 analyzer.py
```

You'll see the main menu:
```
🪙 MEMECOIN ANALYZER
Options:
  [1] Analyze new call
  [2] View source stats
  [3] Exit
```

## Usage

### Analyzing a New Token

1. Select option `[1]` from the main menu
2. Enter the contract address (e.g., `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`)
3. Enter the source name (e.g., "Alpha Group #3")
4. Select blockchain (Solana/BNB, default is Solana)
5. Review the analysis results
6. Record your decision (TRADE/PASS/WATCH)

### Example Analysis Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🪙 TOKEN: $BONK (Bonk)
📍 Source: Alpha Group #3
⏰ Analyzed: 2026-01-15 15:45
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 SAFETY CHECKS:
🟢 Safety Score: 10.0/10 (GOOD)
✅ Mint Authority: REVOKED
✅ Freeze Authority: REVOKED
✅ Top Holder: 0.0% (acceptable)

📊 MARKET DATA:
💧 Liquidity: $1.6M
👥 Holders: N/A
⏰ Age: 1118.1 days
📈 24h Volume: $280.2K
💰 Market Cap: $935.7M
💵 Price: $0.0000105300

✅ No major red flags detected!

🤔 YOUR DECISION:
[T]RADE / [P]ASS / [W]ATCH?
```

### Viewing Source Statistics

Select option `[2]` to see performance stats for all your call sources:

```
📊 SOURCE PERFORMANCE STATISTICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tier   Source                    Calls    Traded   Win%     Avg Gain     Rug%
─────────────────────────────────────────────────────────────────────────────────
🏆 S    Elite Signals             50       45       68.9%      8.5%       4.4%
🥇 A    Alpha Group #3            23       18       55.6%      4.2%       8.7%
🥈 B    Discord Degen             15       12       41.7%      2.1%      13.3%
🥉 C    Random Twitter            8        3        33.3%      0.8%      37.5%
```

## Performance Tracking

The system automatically tracks token performance **every hour in the background** (if you ran `./setup_tracking.sh` during installation). This means whenever you check source stats in the analyzer, the data is fresh and up-to-date!

**What it tracks automatically:**
- Current prices at 1h, 24h, 7d, and 30d intervals
- Max gains and losses observed
- Rug pull detection (liquidity drops or 99%+ crashes)
- Token survival status
- Updates all source statistics with real win rates

**Manual tracking** (if needed):
```bash
# Update all tokens now
python3 performance_tracker.py

# Update only recent 10 tokens
python3 performance_tracker.py --limit 10

# Show summary
python3 performance_tracker.py --summary
```

**Setup automatic tracking** (if you skipped it):
```bash
./setup_tracking.sh
```

See `PERFORMANCE_TRACKING.md` for advanced configuration.

## Safety Score Calculation

The safety score starts at 10.0 and deductions are made for risk factors:

**Critical (-3.0 each):**
- Liquidity < $20K
- Mint authority NOT revoked
- Freeze authority active

**High Risk (-2.0):**
- Top holder > 20%

**Medium Risk (-1.0 each):**
- Token age < 0.5 hours
- Volume/Liquidity ratio < 0.05

**Bonus (+0.5):**
- Liquidity > $100K

## Red Flags

Automatically detected red flags include:

- 🔴 **CRITICAL**: Low liquidity, mint not revoked, freeze active
- 🟠 **HIGH RISK**: Whale concentration
- 🟡 **MEDIUM**: Very new token, low trading activity

## Database Schema

The system uses SQLite with 5 tables:

1. **calls_received**: All tokens you've analyzed
2. **initial_snapshot**: Market data at time of analysis
3. **my_decisions**: Your trading decisions and notes
4. **performance_tracking**: Price tracking over time
5. **source_performance**: Aggregated stats per source

## Testing

Test the database:
```bash
python3 database.py
```

Test the data fetcher:
```bash
python3 data_fetcher.py
```

Run end-to-end test:
```bash
python3 test_e2e.py
```

## Project Structure

```
sweetmemerep/
├── analyzer.py                # Main CLI interface
├── database.py                # SQLite database manager
├── data_fetcher.py            # API data fetching
├── performance_tracker.py     # Automated performance tracking
├── setup_tracking.sh          # One-click setup for hourly tracking
├── requirements.txt           # Python dependencies
├── test_e2e.py               # End-to-end tests
├── README.md                 # This file
├── PERFORMANCE_TRACKING.md   # Performance tracking guide
└── .gitignore                # Git ignore rules
```

## APIs Used

### DexScreener
- **Endpoint**: `https://api.dexscreener.com/latest/dex/tokens/{address}`
- **Data**: Price, liquidity, volume, market cap, pair creation time
- **Rate Limit**: Public, no auth required

### RugCheck
- **Endpoint**: `https://api.rugcheck.xyz/v1/tokens/{address}/report`
- **Data**: Mint/freeze authority, holder distribution, security score
- **Rate Limit**: Public, no auth required

## Tips for Best Results

1. **Always verify contract address** - Double-check before analyzing
2. **Record emotional state honestly** - Helps identify FOMO trades
3. **Track multiple sources** - See which groups provide best calls
4. **Review red flags carefully** - Critical flags should be dealbreakers
5. **Use notes field** - Record your reasoning for future analysis

## Limitations

- Holder count may not be available for all tokens (RugCheck limitation)
- Data accuracy depends on API availability
- Historical price tracking requires manual updates
- No automated trading functionality

## Safety Ratings

- **🟢 GOOD (8.0-10.0)**: Generally safe, minimal red flags
- **🟡 MODERATE (6.0-7.9)**: Some concerns, proceed with caution
- **🟠 RISKY (4.0-5.9)**: Multiple red flags, high risk
- **🔴 DANGEROUS (0.0-3.9)**: Critical issues, avoid

## Contributing

Feel free to submit issues or pull requests to improve the analyzer.

## Disclaimer

This tool is for educational and research purposes only. Always do your own research (DYOR) before making any trading decisions. Cryptocurrency trading carries significant risk of loss.

## License

MIT License - use at your own risk.
