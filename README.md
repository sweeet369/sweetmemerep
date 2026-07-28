# 🪙 Coin Trading Analyzer

A comprehensive CLI tool for analyzing coin trading opportunities across multiple blockchains. Track calls, analyze safety metrics, record decisions, and measure source performance over time.

## Features

- **Multi-Chain Support**: Analyze tokens on Solana, Base, Ethereum, BSC, Polygon, and Arbitrum
- **Real-time Analysis**: Fetch live data from Birdeye with DexScreener fallback
- **Safety Scoring**: Automated safety score (0-10) based on multiple risk factors
- **Smart Money Tracking**: Track profitable wallets and detect when they're holding analyzed tokens
- **Red Flag Detection**: Automatic detection of critical risks (low liquidity, mint authority, whale concentration)
- **Decision Tracking**: Record your trading decisions with notes and emotional state
- **Watchlist Monitoring**: Track tokens marked as "WATCH" and monitor their performance before entering
- **Source Performance**: Track which sources provide the best calls over time
- **Performance Tracking**: 5‑minute time‑series snapshots for active WATCH/TRADE positions
- **Rug Pull Detection**: Automatic detection of rugged tokens via liquidity drops
- **Parallel Processing**: Fast batch updates with configurable worker threads
- **API Health Checks**: Verify API connectivity before running updates
- **SQLite / Supabase**: Local SQLite by default, Supabase (PostgreSQL) if DATABASE_URL is set

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

3. Set your Birdeye API key:
```bash
export BIRDEYE_API_KEY="your_api_key"
```

4. **Set up automatic tracking** (recommended):
```bash
./setup_tracking.sh
```

This sets up automated performance tracking. The tracker runs in the background via cron (Linux) or launchd (macOS).

That's it! Birdeye is required for market data.

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
  [3] Watchlist performance
  [4] Manage tracked wallets
  [5] Add source to existing token
  [6] Exit
```

## Usage

### Analyzing a New Token

1. Select option `[1]` from the main menu
2. Enter the contract address (e.g., `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`)
3. Enter source name(s) - supports multiple sources!
   - Single source: `"Alpha Group #3"`
   - Multiple sources: `"Discord Degen, Twitter Alpha, Wallet_ABC"`
4. Select blockchain (Solana/BNB, default is Solana)
5. Review the analysis results
6. Record your decision (TRADE/PASS/WATCH)

**Multi-Source Tracking:**
- Track which combinations of sources give the best calls
- Each source maintains independent performance stats
- Perfect for comparing signal quality across groups

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

### Monitoring Your Watchlist

Select option `[3]` to see all tokens you marked as "WATCH" and their current performance:

```
👀 WATCHLIST PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Watching 3 token(s)

────────────────────────────────────────────────────────────
[1] $PEPE - Pepe Coin
    📍 Source: Discord Degen
    🔗 4k3Dyjzvzp8eMZWUXbBC...
    🟢 Safety Score: 8.0/10 (GOOD)
    💧 Entry Liquidity: $85.0K
    ⏱️  Added: 2h ago
    📝 Notes: Good early metrics, watching for entry
    📈 Best Performance: +185.00%
    🚀 MAJOR PUMP - Consider entry!
    🔄 Last updated: 15m ago

[2] $BONK - Bonk
    📍 Source: Alpha Calls
    🟢 Safety Score: 9.5/10 (GOOD)
    💧 Entry Liquidity: $1.50M
    ⏱️  Added: 1d ago
    📈 Best Performance: +12.50%
    ✅ Positive movement
    🔄 Last updated: 8m ago

💡 Tip: Tokens showing strong gains may be good entry opportunities!
```

**Watchlist Benefits:**
- Track tokens before committing capital
- Get alerted to major pumps (+100%, +500%, etc.)
- Monitor multiple opportunities simultaneously
- Automatic rug pull detection
- See performance trends over time

### Smart Money Tracking

Select option `[4]` to manage smart money wallets - track profitable traders and get alerted when they're holding tokens you analyze!

**Features:**
- Add wallet addresses with nicknames
- Track performance stats (win rate, average gains, total buys)
- Auto-tier wallets (S/A/B/C) based on performance
- Automatic detection when tracked wallets hold analyzed tokens
- Safety score bonus when smart money is detected

**Example Detection:**
```
💰 SMART MONEY DETECTED:
🟢 Wallet: Elite Trader 1 (S-Tier, 78% win rate, avg +450%)
🟢 Wallet: Degen King (A-Tier, 65% win rate, avg +280%)
✨ Safety score bonus: +1.0 points
```

**How it works:**
1. Add profitable wallet addresses you want to track
2. Update their performance stats (win rate, avg gains)
3. When analyzing tokens, system checks if tracked wallets are top holders
4. Alerts you when smart money is detected
5. Adds bonus points to safety score (1-2 wallets: +1.0, 3+ wallets: +2.0)

**Quick Start:**
```bash
# Run demo setup (creates 3 example wallets)
python3 test_smart_money.py

# Or manually add wallets
python3 analyzer.py
# Select [4] Manage tracked wallets → [1] Add wallet
```

**Import from JSON:**
Create a JSON file with your wallet list:
```json
[
  {"address": "7xKXtg2...", "name": "Elite Trader", "notes": "Consistently profitable"},
  {"address": "GrWRS3Y...", "name": "Whale Watcher", "notes": "Follows big players"}
]
```

Then import: Select [4] → [4] Import from file

### Adding Sources to Existing Tokens

Select option `[5]` to add more sources to tokens you've already analyzed!

**Use Case:**
- Initially got a call from one source
- Later see the same token called by other sources
- Add all sources to track which combinations perform best

**How it works:**
```
1. Select [5] Add source to existing token
2. Enter contract address
3. See current sources: "Discord Degen"
4. Enter new sources: "Twitter Alpha, Telegram Signal"
5. Result: "Discord Degen, Twitter Alpha, Telegram Signal"
```

**Benefits:**
- Compare source quality (which sources call winners early?)
- Track source combinations (do certain pairs work better together?)
- No duplicate entries - automatically skips existing sources
- Updates all source performance stats automatically

**Example:**
```bash
python3 analyzer.py
# Select [5] Add source to existing token

Contract address: DezX...
📋 Token: $BONK - Bonk
📍 Current source(s): Alpha Group #3

Enter additional source(s) to ADD: Twitter Whale, Smart Money Bot
✅ Added 2 new source(s)
📍 Updated source list: Alpha Group #3, Twitter Whale, Smart Money Bot
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
├── database.py                # SQLite/PostgreSQL database manager
├── data_fetcher.py            # API data fetching with caching & fallback
├── performance_tracker.py     # Automated performance tracking with parallel processing
├── app_logger.py              # Structured logging
├── config.py                  # Configuration management
├── display.py                 # UI display utilities
├── setup_tracking.sh          # One-click setup for hourly tracking
├── requirements.txt           # Python dependencies
├── tests/                     # Test suite
│   ├── test_core_logic.py     # Core functionality tests
│   ├── test_goplus.py         # GoPlus API tests
│   ├── test_postgres_integration.py  # PostgreSQL tests
│   └── test_error_paths.py    # Error handling tests
├── README.md                  # This file
├── PERFORMANCE_TRACKING.md    # Performance tracking guide
└── .github/workflows/         # GitHub Actions CI/CD
    └── tracker.yml            # Automated tracking workflow
```

## Multi-Chain Support

The analyzer supports multiple blockchains with automatic chain detection:

### Supported Chains

| Chain | Identifier | Native Token | Notes |
|-------|------------|--------------|-------|
| **Solana** | `solana` | SOL | Primary support, all features |
| **Base** | `base` | ETH | Full support via GoPlus |
| **Ethereum** | `ethereum` | ETH | Full support via GoPlus |
| **BSC** | `bsc` | BNB | Full support via GoPlus |
| **Polygon** | `polygon` | MATIC | Full support via GoPlus |
| **Arbitrum** | `arbitrum` | ETH | Full support via GoPlus |

### Analyzing Tokens on Different Chains

When analyzing a token, you'll be prompted to select the blockchain:

```
Select blockchain:
  [1] Solana (default)
  [2] Base
  [3] Ethereum
  [4] BSC
  [5] Polygon
  [6] Arbitrum
```

Or specify directly in your workflow tools.

### Chain-Specific Considerations

- **Solana**: Fastest analysis, most detailed data from Birdeye
- **EVM Chains** (Base, Ethereum, BSC, Polygon, Arbitrum): Security data from GoPlus, market data from Birdeye

## APIs Used

### Birdeye (Primary)
- **Data**: Price, liquidity, volume, market cap, holders
- **Auth**: API key required (`BIRDEYE_API_KEY`)
- **Chains**: All supported chains

### GoPlus Security (Cross-Chain)
- **Data**: Mint/freeze authority, holder distribution, taxes, honeypot signals
- **Rate Limit**: Public, no auth required
- **Chains**: All supported chains

### DexScreener (Fallback)
- **Data**: Price, liquidity, volume (used when Birdeye fails)
- **Auth**: None required
- **Chains**: All supported chains

## Advanced Features

### Parallel Processing

Speed up batch updates with parallel API calls:

```bash
# Use 5 parallel workers (default is 3)
python3 performance_tracker.py --workers 5

# Use sequential processing
python3 performance_tracker.py --sequential
```

### API Health Checks

Verify API connectivity before running updates:

```bash
python3 performance_tracker.py --health-check
```

### Dead Letter Queue

Failed token updates are logged for later analysis:

```bash
# View failed updates
python3 performance_tracker.py --show-dead-letter

# Clear the queue
python3 performance_tracker.py --clear-dead-letter
```

### Request Caching

API responses are cached for 60 seconds to reduce redundant calls:
- Same token queried multiple times in quick succession uses cache
- Automatic cache expiration and cleanup
- Improves performance and reduces API rate limit hits

## Tips for Best Results

1. **Always verify contract address** - Double-check before analyzing
2. **Record emotional state honestly** - Helps identify FOMO trades
3. **Track multiple sources** - See which groups provide best calls
4. **Review red flags carefully** - Critical flags should be dealbreakers
5. **Use notes field** - Record your reasoning for future analysis

## Limitations

- Holder count may not be available for all tokens (GoPlus limitation)
- Data accuracy depends on API availability
- Historical price tracking requires manual updates
- No automated trading functionality
- Token age estimation may be inaccurate for some chains
- Some advanced security features require higher-tier API access

## Web Interface 🌐

A beautiful web interface is now available! No more terminal commands needed.

### Starting the Web App

```bash
python3 web_app.py
```

Then open your browser and go to: **http://localhost:5001**

### Features

- **📊 Dashboard** - View your watchlist with pretty cards and stats
- **➕ Add Token** - Simple form to analyze new tokens
- **🔍 Token Details** - Full analysis with market data and security checks
- **📈 Sources** - Track which sources give the best calls
- **📱 Mobile Friendly** - Works on your phone

### Screenshots

**Dashboard:**
- Stats cards showing total tracked, watching, and active trades
- Watchlist with token cards showing safety scores and market cap
- Top performing sources table

**Add Token:**
- Simple form with contract address, blockchain selector, and source
- Supports all 6 blockchains (Solana, Base, Ethereum, BSC, Polygon, Arbitrum)

**Token Detail:**
- Market data (price, market cap, liquidity, volume)
- Security analysis (mint/freeze authority, top holder %)
- Update decision buttons (WATCH/TRADE/PASS)
- Performance history table

## Testing

Run the test suite:

```bash
# Run all tests
python3 -m pytest tests/

# Run specific test files
python3 -m pytest tests/test_core_logic.py
python3 -m pytest tests/test_goplus.py
python3 -m pytest tests/test_error_paths.py

# Run PostgreSQL integration tests (requires DATABASE_URL)
export DATABASE_URL="postgresql://..."
python3 -m pytest tests/test_postgres_integration.py
```

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
