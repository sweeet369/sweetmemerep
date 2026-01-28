# Project Memory - Memecoin Trading Analyzer

## Project Overview
A CLI tool for analyzing memecoin trading opportunities on Solana and BNB Chain. Tracks calls from various sources, analyzes safety metrics, records trading decisions, and measures source performance.

## Tech Stack
- **Language:** Python 3
- **Database:** Supabase (PostgreSQL) for cloud, SQLite for local
- **APIs:** Birdeye, GoPlus
- **Deployment:** GitHub Actions for automated tracking

## Key Decisions

### 2026-01-25: Added Enhanced Trading Analysis Features
- Added honeypot risk detection (LOW/MEDIUM/HIGH)
- Added token tax estimation (buy/sell fees from GoPlus)
- Added holder distribution analysis (concentration, whale count)
- Added momentum indicators (buy/sell pressure, price momentum, volume trend)
- Improved smart money wallet analysis with better sorting

### Architecture Decisions
- Birdeye API as the only market data source
- GoPlus for security data (mint/freeze authority, holder distribution)
- Source normalization to lowercase for consistent tracking

## Learnings

### API Behavior
- Birdeye doesn't provide pair creation time (token age shows 0.0h)
- GoPlus returns 0% for top holders on very large tokens (like BONK)
- Token taxes are estimated from GoPlus signals

### User Preferences
- User is not a coder - explain things simply
- When errors are pasted, just fix them without asking unnecessary questions
- Ask clarifying questions before building new features

## Known Issues
- Token age shows 0.0h when using Birdeye (no creation timestamp)
- Holder distribution may show "UNKNOWN" for very large tokens

## File Structure
```
analyzer.py           - Main CLI interface
database.py           - Database manager (SQLite + PostgreSQL)
data_fetcher.py       - API data fetching with new analysis features
performance_tracker.py - Auto-tracks prices (runs in GitHub Actions)
```
