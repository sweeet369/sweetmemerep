-- Supabase Migration v2: Performance Optimizations
-- Run this in Supabase SQL Editor
-- ================================================

-- STEP 1: Convert TEXT timestamps to TIMESTAMPTZ
-- ================================================
DO $$
BEGIN
    -- calls_received.timestamp_received
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'calls_received'
               AND column_name = 'timestamp_received'
               AND data_type = 'text') THEN
        ALTER TABLE calls_received
            ALTER COLUMN timestamp_received TYPE TIMESTAMPTZ
            USING timestamp_received::TIMESTAMPTZ;
        RAISE NOTICE 'Converted calls_received.timestamp_received to TIMESTAMPTZ';
    END IF;

    -- initial_snapshot.snapshot_timestamp
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'initial_snapshot'
               AND column_name = 'snapshot_timestamp'
               AND data_type = 'text') THEN
        ALTER TABLE initial_snapshot
            ALTER COLUMN snapshot_timestamp TYPE TIMESTAMPTZ
            USING snapshot_timestamp::TIMESTAMPTZ;
        RAISE NOTICE 'Converted initial_snapshot.snapshot_timestamp to TIMESTAMPTZ';
    END IF;

    -- my_decisions.timestamp_decision
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'my_decisions'
               AND column_name = 'timestamp_decision'
               AND data_type = 'text') THEN
        ALTER TABLE my_decisions
            ALTER COLUMN timestamp_decision TYPE TIMESTAMPTZ
            USING timestamp_decision::TIMESTAMPTZ;
        RAISE NOTICE 'Converted my_decisions.timestamp_decision to TIMESTAMPTZ';
    END IF;

    -- my_decisions.entry_timestamp
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'my_decisions'
               AND column_name = 'entry_timestamp'
               AND data_type = 'text') THEN
        ALTER TABLE my_decisions
            ALTER COLUMN entry_timestamp TYPE TIMESTAMPTZ
            USING NULLIF(entry_timestamp, '')::TIMESTAMPTZ;
        RAISE NOTICE 'Converted my_decisions.entry_timestamp to TIMESTAMPTZ';
    END IF;

    -- performance_tracking.last_updated
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'performance_tracking'
               AND column_name = 'last_updated'
               AND data_type = 'text') THEN
        ALTER TABLE performance_tracking
            ALTER COLUMN last_updated TYPE TIMESTAMPTZ
            USING last_updated::TIMESTAMPTZ;
        RAISE NOTICE 'Converted performance_tracking.last_updated to TIMESTAMPTZ';
    END IF;

    -- source_performance.last_updated
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'source_performance'
               AND column_name = 'last_updated'
               AND data_type = 'text') THEN
        ALTER TABLE source_performance
            ALTER COLUMN last_updated TYPE TIMESTAMPTZ
            USING last_updated::TIMESTAMPTZ;
        RAISE NOTICE 'Converted source_performance.last_updated to TIMESTAMPTZ';
    END IF;

    -- tracked_wallets.date_added
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'tracked_wallets'
               AND column_name = 'date_added'
               AND data_type = 'text') THEN
        ALTER TABLE tracked_wallets
            ALTER COLUMN date_added TYPE TIMESTAMPTZ
            USING date_added::TIMESTAMPTZ;
        RAISE NOTICE 'Converted tracked_wallets.date_added to TIMESTAMPTZ';
    END IF;
END $$;

-- STEP 2: Convert TEXT boolean columns to BOOLEAN
-- ================================================
DO $$
BEGIN
    -- performance_tracking.token_still_alive: 'yes'/'no' -> BOOLEAN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'performance_tracking'
               AND column_name = 'token_still_alive'
               AND data_type = 'text') THEN

        ALTER TABLE performance_tracking
            ADD COLUMN token_still_alive_bool BOOLEAN DEFAULT TRUE;

        UPDATE performance_tracking
            SET token_still_alive_bool = (token_still_alive = 'yes');

        ALTER TABLE performance_tracking
            DROP COLUMN token_still_alive;

        ALTER TABLE performance_tracking
            RENAME COLUMN token_still_alive_bool TO token_still_alive;

        RAISE NOTICE 'Converted performance_tracking.token_still_alive to BOOLEAN';
    END IF;

    -- performance_tracking.rug_pull_occurred: 'yes'/'no' -> BOOLEAN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'performance_tracking'
               AND column_name = 'rug_pull_occurred'
               AND data_type = 'text') THEN

        ALTER TABLE performance_tracking
            ADD COLUMN rug_pull_occurred_bool BOOLEAN DEFAULT FALSE;

        UPDATE performance_tracking
            SET rug_pull_occurred_bool = (rug_pull_occurred = 'yes');

        ALTER TABLE performance_tracking
            DROP COLUMN rug_pull_occurred;

        ALTER TABLE performance_tracking
            RENAME COLUMN rug_pull_occurred_bool TO rug_pull_occurred;

        RAISE NOTICE 'Converted performance_tracking.rug_pull_occurred to BOOLEAN';
    END IF;
END $$;

-- STEP 3: Create optimized indexes
-- ================================================

-- STEP 2b: Create performance_history table if missing
-- ================================================
CREATE TABLE IF NOT EXISTS performance_history (
    history_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls_received(call_id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_status VARCHAR(20) NOT NULL,
    reference_price REAL,
    price_usd REAL,
    liquidity_usd REAL,
    total_liquidity REAL,
    market_cap REAL,
    gain_loss_pct REAL,
    price_change_pct REAL,
    liquidity_change_pct REAL,
    market_cap_change_pct REAL,
    token_still_alive BOOLEAN DEFAULT TRUE,
    rug_pull_occurred BOOLEAN DEFAULT FALSE
);

-- Foreign key indexes (if not exist)
CREATE INDEX IF NOT EXISTS idx_initial_snapshot_call_id ON initial_snapshot(call_id);
CREATE INDEX IF NOT EXISTS idx_my_decisions_call_id ON my_decisions(call_id);
CREATE INDEX IF NOT EXISTS idx_performance_tracking_call_id ON performance_tracking(call_id);
CREATE INDEX IF NOT EXISTS idx_performance_history_call_id ON performance_history(call_id);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_calls_received_contract ON calls_received(contract_address);
CREATE INDEX IF NOT EXISTS idx_calls_received_source ON calls_received(source);
CREATE INDEX IF NOT EXISTS idx_tracked_wallets_address ON tracked_wallets(wallet_address);

-- Decision type index (frequently filtered)
CREATE INDEX IF NOT EXISTS idx_decisions_type ON my_decisions(my_decision);

-- Performance tracking indexes
CREATE INDEX IF NOT EXISTS idx_perf_last_updated ON performance_tracking(last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_performance_history_timestamp ON performance_history(timestamp DESC);

-- Timestamp-based indexes for time queries
CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON calls_received(timestamp_received DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON initial_snapshot(snapshot_timestamp DESC);

-- Covering index for tracker joins (avoids table lookup)
CREATE INDEX IF NOT EXISTS idx_snapshot_covering ON initial_snapshot(call_id, snapshot_timestamp, price_usd);

-- STEP 4: Create partial indexes for hot query paths
-- ================================================

-- Open trades (TRADE with no exit) - used by performance_tracker
CREATE INDEX IF NOT EXISTS idx_decisions_open_trades
    ON my_decisions(call_id)
    WHERE my_decision = 'TRADE' AND (actual_exit_price IS NULL OR actual_exit_price = 0);

-- Watch decisions - used by performance_tracker
CREATE INDEX IF NOT EXISTS idx_decisions_watch
    ON my_decisions(call_id)
    WHERE my_decision = 'WATCH';

-- Live tokens (after BOOLEAN conversion)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'performance_tracking'
               AND column_name = 'token_still_alive'
               AND data_type = 'boolean') THEN
        CREATE INDEX IF NOT EXISTS idx_perf_alive
            ON performance_tracking(call_id)
            WHERE token_still_alive = TRUE;

        CREATE INDEX IF NOT EXISTS idx_perf_rugs
            ON performance_tracking(call_id)
            WHERE rug_pull_occurred = TRUE;

        RAISE NOTICE 'Created partial indexes for BOOLEAN columns';
    END IF;
END $$;

-- STEP 5: Enable useful extensions
-- ================================================
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- STEP 6: Verify changes
-- ================================================
SELECT 'MIGRATION COMPLETE' as status;

-- Show all indexes on our tables
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('calls_received', 'initial_snapshot', 'my_decisions', 'performance_tracking', 'source_performance', 'tracked_wallets')
ORDER BY tablename, indexname;

-- Show column types to verify conversions
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('calls_received', 'initial_snapshot', 'my_decisions', 'performance_tracking', 'source_performance', 'tracked_wallets')
AND column_name IN ('timestamp_received', 'snapshot_timestamp', 'timestamp_decision', 'entry_timestamp', 'last_updated', 'date_added', 'token_still_alive', 'rug_pull_occurred')
ORDER BY table_name, column_name;
