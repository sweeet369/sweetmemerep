# Project Status - Memecoin Trading Analyzer

**Last Updated:** January 21, 2026

---

## What Was Accomplished Today

### Cloud Setup (COMPLETED)
1. **Supabase Database** - Set up cloud PostgreSQL database
   - Project: `ooccknyalgowtmfvjpij`
   - Tables created: calls_received, initial_snapshot, my_decisions, performance_tracking, source_performance, tracked_wallets

2. **GitHub Actions Tracker** - Runs every 5 minutes automatically
   - Workflow file: `.github/workflows/tracker.yml`
   - Uses `DATABASE_URL` secret (Transaction Pooler connection)
   - Connection string format: `postgresql://postgres.ooccknyalgowtmfvjpij:PASSWORD@aws-1-eu-central-1.pooler.supabase.com:6543/postgres`

3. **Code Updates**
   - `database.py` - Now supports both SQLite (local) and PostgreSQL (Supabase)
   - Uses `DATABASE_URL` environment variable to switch between them
   - `requirements.txt` - Added `psycopg2-binary`

4. **Files Created**
   - `supabase_setup.sql` - SQL to create tables in Supabase
   - `migrate_to_supabase.py` - Script to migrate local data to cloud
   - `.github/workflows/tracker.yml` - GitHub Actions workflow

---

## Current Architecture

```
LOCAL (your Mac):
  analyzer.py → SQLite database (memecoin_analyzer.db)

CLOUD (GitHub Actions + Supabase):
  performance_tracker.py → Supabase PostgreSQL (runs every 5 min)
```

**Problem:** Local and cloud databases are separate! Tokens analyzed locally won't be tracked by the cloud tracker.

---

## Known Issues To Fix

### High Priority
1. **Database Sync Issue** - Local app uses SQLite, cloud uses Supabase
   - **Fix needed:** Update local app to also use Supabase (set DATABASE_URL locally)
   - Or: Create sync mechanism between local and cloud

2. **Supabase Password Exposed** - Password was shared in conversation
   - **Fix needed:** Reset password in Supabase → Settings → Database
   - Then update GitHub secret with new password

### Medium Priority
3. **No Web Interface** - Can only view data via local CLI app
   - Could use Supabase dashboard to view tables directly
   - Or build a simple web dashboard later

4. **Source Stats Empty** - Fresh Supabase database has no historical data
   - Will populate as you analyze new tokens

### Low Priority / Future Enhancements
5. **5-minute tracking interval** - GitHub Actions can sometimes have delays
6. **No notifications** - No alerts when tokens pump or rug

---

## How To Continue Development

### To use local app with cloud database:
```bash
export DATABASE_URL='postgresql://postgres.ooccknyalgowtmfvjpij:NEW_PASSWORD@aws-1-eu-central-1.pooler.supabase.com:6543/postgres'
python3 analyzer.py
```

### To check GitHub Actions:
- Go to: https://github.com/sweeet369/sweetmemerep/actions
- Look for "Performance Tracker" workflow runs

### To view data in Supabase:
- Go to: https://supabase.com/dashboard
- Select your project → Table Editor

### To reset Supabase password:
1. Supabase Dashboard → Settings → Database
2. Click "Reset database password"
3. Update GitHub secret: Settings → Secrets → Actions → DATABASE_URL

---

## File Structure

```
sweetmemerep-1/
├── analyzer.py           # Main CLI app (run this)
├── database.py           # Database layer (SQLite + PostgreSQL)
├── data_fetcher.py       # API calls to DexScreener + RugCheck
├── performance_tracker.py # Auto-updates token prices
├── requirements.txt      # Python dependencies
├── supabase_setup.sql    # SQL for creating tables
├── migrate_to_supabase.py # Migration script
├── .github/
│   └── workflows/
│       └── tracker.yml   # GitHub Actions config
└── CLAUDE.md             # Instructions for Claude
```

---

## Quick Commands

```bash
# Run the main analyzer
python3 analyzer.py

# Run tracker manually (local)
python3 performance_tracker.py

# Set cloud database for local use
export DATABASE_URL='postgresql://postgres.ooccknyalgowtmfvjpij:PASSWORD@aws-1-eu-central-1.pooler.supabase.com:6543/postgres'
```

---

## Notes for Next Session

- User prefers simple explanations (not a coder)
- When user pastes errors, just fix them without asking unnecessary questions
- Ask clarifying questions before building new features
