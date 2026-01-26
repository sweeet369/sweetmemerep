-- Supabase Table Setup for Memecoin Tracker (v2)
-- Run this in the Supabase SQL Editor
-- For existing databases, run supabase_migration_v2.sql instead

-- Table 1: calls_received
CREATE TABLE IF NOT EXISTS calls_received (
    call_id SERIAL PRIMARY KEY,
    timestamp_received TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contract_address VARCHAR(64) UNIQUE NOT NULL,
    token_symbol VARCHAR(20),
    token_name VARCHAR(100),
    source VARCHAR(200),
    blockchain VARCHAR(20) DEFAULT 'Solana'
);

-- Table 2: initial_snapshot
CREATE TABLE IF NOT EXISTS initial_snapshot (
    snapshot_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    liquidity_usd REAL,
    holder_count INTEGER,
    top_holder_percent REAL,
    top_10_holders_percent REAL,
    token_age_hours REAL,
    market_cap REAL,
    volume_24h REAL,
    price_usd REAL,
    mint_authority_revoked BOOLEAN,
    freeze_authority_revoked BOOLEAN,
    rugcheck_score REAL,
    safety_score REAL,
    raw_data JSONB,
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
    main_pool_dex VARCHAR(50)
);

-- Table 3: my_decisions
CREATE TABLE IF NOT EXISTS my_decisions (
    decision_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    timestamp_decision TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    my_decision VARCHAR(20) NOT NULL,
    trade_size_usd REAL,
    entry_price REAL,
    entry_timestamp TIMESTAMPTZ,
    reasoning_notes TEXT,
    emotional_state VARCHAR(50),
    confidence_level INTEGER CHECK (confidence_level BETWEEN 1 AND 10),
    chart_assessment TEXT,
    actual_exit_price REAL,
    hold_duration_hours REAL
);

-- Table 4: performance_tracking
CREATE TABLE IF NOT EXISTS performance_tracking (
    tracking_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price_1h_later REAL,
    price_24h_later REAL,
    price_7d_later REAL,
    price_30d_later REAL,
    current_mcap REAL,
    current_liquidity REAL,
    max_gain_observed REAL,
    max_loss_observed REAL,
    token_still_alive BOOLEAN DEFAULT TRUE,
    rug_pull_occurred BOOLEAN DEFAULT FALSE,
    checkpoint_type VARCHAR(10),
    max_price_since_entry REAL,
    min_price_since_entry REAL
);

-- Table 5: source_performance
CREATE TABLE IF NOT EXISTS source_performance (
    source_id SERIAL PRIMARY KEY,
    source_name VARCHAR(200) UNIQUE NOT NULL,
    total_calls INTEGER DEFAULT 0,
    calls_traded INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_max_gain REAL DEFAULT 0.0,
    rug_rate REAL DEFAULT 0.0,
    hit_rate REAL DEFAULT 0.0,
    tier VARCHAR(1) DEFAULT 'C',
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table 6: tracked_wallets
CREATE TABLE IF NOT EXISTS tracked_wallets (
    wallet_id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(64) UNIQUE NOT NULL,
    wallet_name VARCHAR(100) NOT NULL,
    total_tracked_buys INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_gain REAL DEFAULT 0.0,
    tier VARCHAR(1) DEFAULT 'C',
    notes TEXT,
    date_added TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

-- Foreign key indexes
CREATE INDEX IF NOT EXISTS idx_initial_snapshot_call_id ON initial_snapshot(call_id);
CREATE INDEX IF NOT EXISTS idx_my_decisions_call_id ON my_decisions(call_id);
CREATE INDEX IF NOT EXISTS idx_performance_tracking_call_id ON performance_tracking(call_id);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_calls_received_contract ON calls_received(contract_address);
CREATE INDEX IF NOT EXISTS idx_calls_received_source ON calls_received(source);
CREATE INDEX IF NOT EXISTS idx_tracked_wallets_address ON tracked_wallets(wallet_address);

-- Decision type index
CREATE INDEX IF NOT EXISTS idx_decisions_type ON my_decisions(my_decision);

-- Time-based indexes
CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON calls_received(timestamp_received DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON initial_snapshot(snapshot_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perf_last_updated ON performance_tracking(last_updated DESC);

-- Covering index for tracker joins
CREATE INDEX IF NOT EXISTS idx_snapshot_covering ON initial_snapshot(call_id, snapshot_timestamp, price_usd);

-- Partial indexes for hot query paths
CREATE INDEX IF NOT EXISTS idx_decisions_open_trades
    ON my_decisions(call_id)
    WHERE my_decision = 'TRADE' AND (actual_exit_price IS NULL OR actual_exit_price = 0);

CREATE INDEX IF NOT EXISTS idx_decisions_watch
    ON my_decisions(call_id)
    WHERE my_decision = 'WATCH';

CREATE INDEX IF NOT EXISTS idx_perf_alive
    ON performance_tracking(call_id)
    WHERE token_still_alive = TRUE;

CREATE INDEX IF NOT EXISTS idx_perf_rugs
    ON performance_tracking(call_id)
    WHERE rug_pull_occurred = TRUE;

-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
