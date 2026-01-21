-- Supabase Table Setup for Memecoin Tracker
-- Run this in the Supabase SQL Editor

-- Table 1: calls_received
CREATE TABLE IF NOT EXISTS calls_received (
    call_id SERIAL PRIMARY KEY,
    timestamp_received TEXT NOT NULL,
    contract_address TEXT UNIQUE NOT NULL,
    token_symbol TEXT,
    token_name TEXT,
    source TEXT,
    blockchain TEXT DEFAULT 'Solana'
);

-- Table 2: initial_snapshot
CREATE TABLE IF NOT EXISTS initial_snapshot (
    snapshot_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    snapshot_timestamp TEXT NOT NULL,
    liquidity_usd REAL,
    holder_count INTEGER,
    top_holder_percent REAL,
    top_10_holders_percent REAL,
    token_age_hours REAL,
    market_cap REAL,
    volume_24h REAL,
    price_usd REAL,
    mint_authority_revoked INTEGER,
    freeze_authority_revoked INTEGER,
    rugcheck_score REAL,
    safety_score REAL,
    raw_data TEXT,
    price_vs_atl_percent REAL,
    buy_count_24h INTEGER,
    sell_count_24h INTEGER,
    price_change_5m REAL,
    price_change_1h REAL,
    price_change_24h REAL,
    all_time_high REAL,
    all_time_low REAL,
    liquidity_locked_percent REAL,
    main_pool_liquidity REAL,
    total_liquidity REAL,
    main_pool_dex TEXT
);

-- Table 3: my_decisions
CREATE TABLE IF NOT EXISTS my_decisions (
    decision_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    timestamp_decision TEXT NOT NULL,
    my_decision TEXT NOT NULL,
    trade_size_usd REAL,
    entry_price REAL,
    entry_timestamp TEXT,
    reasoning_notes TEXT,
    emotional_state TEXT,
    confidence_level INTEGER,
    chart_assessment TEXT,
    actual_exit_price REAL,
    hold_duration_hours REAL
);

-- Table 4: performance_tracking
CREATE TABLE IF NOT EXISTS performance_tracking (
    tracking_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    last_updated TEXT NOT NULL,
    price_1h_later REAL,
    price_24h_later REAL,
    price_7d_later REAL,
    price_30d_later REAL,
    current_mcap REAL,
    current_liquidity REAL,
    max_gain_observed REAL,
    max_loss_observed REAL,
    token_still_alive TEXT,
    rug_pull_occurred TEXT,
    checkpoint_type TEXT,
    max_price_since_entry REAL,
    min_price_since_entry REAL
);

-- Table 5: source_performance
CREATE TABLE IF NOT EXISTS source_performance (
    source_id SERIAL PRIMARY KEY,
    source_name TEXT UNIQUE NOT NULL,
    total_calls INTEGER DEFAULT 0,
    calls_traded INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_max_gain REAL DEFAULT 0.0,
    rug_rate REAL DEFAULT 0.0,
    hit_rate REAL DEFAULT 0.0,
    tier TEXT DEFAULT 'C',
    last_updated TEXT NOT NULL
);

-- Table 6: tracked_wallets
CREATE TABLE IF NOT EXISTS tracked_wallets (
    wallet_id SERIAL PRIMARY KEY,
    wallet_address TEXT UNIQUE NOT NULL,
    wallet_name TEXT NOT NULL,
    total_tracked_buys INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_gain REAL DEFAULT 0.0,
    tier TEXT DEFAULT 'C',
    notes TEXT,
    date_added TEXT NOT NULL
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_calls_contract ON calls_received(contract_address);
CREATE INDEX IF NOT EXISTS idx_snapshot_call ON initial_snapshot(call_id);
CREATE INDEX IF NOT EXISTS idx_decisions_call ON my_decisions(call_id);
CREATE INDEX IF NOT EXISTS idx_performance_call ON performance_tracking(call_id);
