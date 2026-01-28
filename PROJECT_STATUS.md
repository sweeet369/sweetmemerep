# Project Status - Memecoin Trading Analyzer

**Last Updated:** January 23, 2026

---

## REMINDER: Reset Supabase Password!
Your database password was exposed in a conversation. When you have time:
1. Go to Supabase → Settings → Database → Reset database password
2. Update GitHub secret (Settings → Secrets → Actions → DATABASE_URL) with new password
3. Update your local `.env` file with new password
4. Delete this reminder once done

---

## What's Working Now

### Local App
- **Analyzer** (`python3 analyzer.py`) - Fully working
- **Uses Supabase** - Local and cloud now share the same database
- **Uses Birdeye API** - Market data source
- **`.env` file** - Stores your secrets locally (not committed to git)

### Cloud Tracker (GitHub Actions)
- **Runs every 5 minutes** automatically
- **Uses Supabase** - Same database as local
- **Uses Birdeye API** - More accurate data
- **Secrets configured:**
  - `DATABASE_URL` - Supabase connection
  - `BIRDEYE_API_KEY` - Birdeye API access

---

## Data Sources

| Source | Purpose | Status |
|--------|---------|--------|
| **Birdeye** (Primary) | Price, liquidity, volume, market cap, holders | ✅ Working |
| **GoPlus** | Security (mint/freeze authority, top holders) | ✅ Working |

---

## Tracking Logic

| Decision | When tracking STARTS | When tracking STOPS |
|----------|---------------------|---------------------|
| **TRADE** | When you choose TRADE | When you record exit |
| **WATCH** | When you choose WATCH | When you remove from watchlist |
| **PASS** | Never tracked | N/A |

---

## Files & Structure

```
sweetmemerep-1/
├── analyzer.py           # Main CLI app
├── database.py           # Database (SQLite + PostgreSQL support)
├── data_fetcher.py       # Birdeye + GoPlus APIs
├── performance_tracker.py # Auto-tracks prices (runs in cloud)
├── .env                  # Your local secrets (NOT in git)
├── .env.example          # Template for .env
├── requirements.txt      # Python dependencies
├── .github/workflows/
│   └── tracker.yml       # GitHub Actions config
└── PROJECT_STATUS.md     # This file
```

---

## How to Run Locally

```bash
# Navigate to project
cd ~/Desktop/sweetmemerep-1

# Run the main analyzer
python3 analyzer.py

# Run tracker manually (optional - cloud does this automatically)
python3 performance_tracker.py
```

---

## How to Monitor Cloud Tracker

1. Go to: https://github.com/sweeet369/sweetmemerep/actions
2. Look for "Performance Tracker" runs
3. Green checkmark = success
4. Click on a run to see details/logs

---

## How to View Data in Supabase

1. Go to: https://supabase.com/dashboard
2. Select your project
3. Click "Table Editor" in left sidebar
4. Browse your tables: calls_received, my_decisions, etc.

---

## Secrets Reference

**IMPORTANT:** Never put actual secrets in this file! Use the `.env` file (which is not committed to git).

### Local (.env file)
See `.env.example` for the format. Your actual `.env` file should contain:
- `DATABASE_URL` - Your Supabase connection string
- `BIRDEYE_API_KEY` - Your Birdeye API key

### GitHub Secrets
Configure these in: GitHub → Settings → Secrets → Actions
- `DATABASE_URL` - Same as your local .env
- `BIRDEYE_API_KEY` - Same as your local .env

---

## Notes for Next Session

- User prefers simple explanations (not a coder)
- When user pastes errors, just fix them without asking unnecessary questions
- Ask clarifying questions before building new features
