#!/usr/bin/env python3
"""
Migrate data from local SQLite to Supabase (PostgreSQL).

Usage:
    1. Set your DATABASE_URL environment variable with your Supabase connection string
    2. Run: python migrate_to_supabase.py

Example:
    export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres"
    python migrate_to_supabase.py
"""

import os
import sqlite3
import sys

# Check for DATABASE_URL before importing psycopg2
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set!")
    print("")
    print("To set it, run this command (replace with your actual Supabase connection string):")
    print("")
    print('  export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres"')
    print("")
    print("You can find this in Supabase: Project Settings → Database → Connection string → URI")
    sys.exit(1)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 not installed!")
    print("")
    print("Install it with:")
    print("  pip install psycopg2-binary")
    sys.exit(1)


# Path to local SQLite database
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memecoin_analyzer.db")


def migrate():
    """Migrate all data from SQLite to PostgreSQL."""

    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_DB_PATH}")
        print("Nothing to migrate!")
        sys.exit(1)

    print("=" * 60)
    print("MIGRATING DATA TO SUPABASE")
    print("=" * 60)

    # Connect to SQLite
    print(f"\n📁 Connecting to SQLite: {SQLITE_DB_PATH}")
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL
    print(f"☁️  Connecting to Supabase...")
    pg_conn = psycopg2.connect(DATABASE_URL)
    pg_cursor = pg_conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Migrate calls_received
        print("\n📋 Migrating calls_received...")
        sqlite_cursor.execute("SELECT * FROM calls_received")
        rows = sqlite_cursor.fetchall()
        count = 0
        for row in rows:
            try:
                pg_cursor.execute("""
                    INSERT INTO calls_received
                    (call_id, timestamp_received, contract_address, token_symbol, token_name, source, blockchain)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (contract_address) DO NOTHING
                """, (row['call_id'], row['timestamp_received'], row['contract_address'],
                      row['token_symbol'], row['token_name'], row['source'], row['blockchain']))
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")
        pg_conn.commit()
        print(f"  ✅ Migrated {count} calls")

        # Migrate initial_snapshot
        print("\n📊 Migrating initial_snapshot...")
        sqlite_cursor.execute("SELECT * FROM initial_snapshot")
        rows = sqlite_cursor.fetchall()
        count = 0
        for row in rows:
            try:
                pg_cursor.execute("""
                    INSERT INTO initial_snapshot
                    (snapshot_id, call_id, snapshot_timestamp, liquidity_usd, holder_count,
                     top_holder_percent, top_10_holders_percent, token_age_hours, market_cap,
                     volume_24h, price_usd, mint_authority_revoked, freeze_authority_revoked,
                     rugcheck_score, safety_score, raw_data, price_vs_atl_percent, buy_count_24h,
                     sell_count_24h, price_change_5m, price_change_1h, price_change_24h,
                     all_time_high, all_time_low, liquidity_locked_percent, main_pool_liquidity,
                     total_liquidity, main_pool_dex)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (row['snapshot_id'], row['call_id'], row['snapshot_timestamp'],
                      row['liquidity_usd'], row['holder_count'], row['top_holder_percent'],
                      row['top_10_holders_percent'], row['token_age_hours'], row['market_cap'],
                      row['volume_24h'], row['price_usd'], row['mint_authority_revoked'],
                      row['freeze_authority_revoked'], row['rugcheck_score'], row['safety_score'],
                      row['raw_data'], row.get('price_vs_atl_percent'), row.get('buy_count_24h'),
                      row.get('sell_count_24h'), row.get('price_change_5m'), row.get('price_change_1h'),
                      row.get('price_change_24h'), row.get('all_time_high'), row.get('all_time_low'),
                      row.get('liquidity_locked_percent'), row.get('main_pool_liquidity'),
                      row.get('total_liquidity'), row.get('main_pool_dex')))
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")
        pg_conn.commit()
        print(f"  ✅ Migrated {count} snapshots")

        # Migrate my_decisions
        print("\n🎯 Migrating my_decisions...")
        sqlite_cursor.execute("SELECT * FROM my_decisions")
        rows = sqlite_cursor.fetchall()
        count = 0
        for row in rows:
            try:
                pg_cursor.execute("""
                    INSERT INTO my_decisions
                    (decision_id, call_id, timestamp_decision, my_decision, trade_size_usd,
                     entry_price, entry_timestamp, reasoning_notes, emotional_state, confidence_level,
                     chart_assessment, actual_exit_price, hold_duration_hours)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (row['decision_id'], row['call_id'], row['timestamp_decision'],
                      row['my_decision'], row['trade_size_usd'], row['entry_price'],
                      row.get('entry_timestamp'), row['reasoning_notes'], row['emotional_state'],
                      row['confidence_level'], row.get('chart_assessment'), row.get('actual_exit_price'),
                      row.get('hold_duration_hours')))
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")
        pg_conn.commit()
        print(f"  ✅ Migrated {count} decisions")

        # Migrate performance_tracking
        print("\n📈 Migrating performance_tracking...")
        sqlite_cursor.execute("SELECT * FROM performance_tracking")
        rows = sqlite_cursor.fetchall()
        count = 0
        for row in rows:
            try:
                pg_cursor.execute("""
                    INSERT INTO performance_tracking
                    (tracking_id, call_id, last_updated, price_1h_later, price_24h_later,
                     price_7d_later, price_30d_later, current_mcap, current_liquidity,
                     max_gain_observed, max_loss_observed, token_still_alive, rug_pull_occurred,
                     checkpoint_type, max_price_since_entry, min_price_since_entry)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (row['tracking_id'], row['call_id'], row['last_updated'],
                      row['price_1h_later'], row['price_24h_later'], row['price_7d_later'],
                      row['price_30d_later'], row.get('current_mcap'), row.get('current_liquidity'),
                      row['max_gain_observed'], row['max_loss_observed'], row['token_still_alive'],
                      row['rug_pull_occurred'], row.get('checkpoint_type'),
                      row.get('max_price_since_entry'), row.get('min_price_since_entry')))
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")
        pg_conn.commit()
        print(f"  ✅ Migrated {count} performance records")

        # Migrate source_performance
        print("\n🏆 Migrating source_performance...")
        sqlite_cursor.execute("SELECT * FROM source_performance")
        rows = sqlite_cursor.fetchall()
        count = 0
        for row in rows:
            try:
                pg_cursor.execute("""
                    INSERT INTO source_performance
                    (source_id, source_name, total_calls, calls_traded, win_rate, avg_max_gain,
                     rug_rate, hit_rate, tier, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_name) DO NOTHING
                """, (row['source_id'], row['source_name'], row['total_calls'],
                      row['calls_traded'], row['win_rate'], row['avg_max_gain'],
                      row['rug_rate'], row.get('hit_rate', 0), row['tier'], row['last_updated']))
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")
        pg_conn.commit()
        print(f"  ✅ Migrated {count} source records")

        # Migrate tracked_wallets
        print("\n👛 Migrating tracked_wallets...")
        sqlite_cursor.execute("SELECT * FROM tracked_wallets")
        rows = sqlite_cursor.fetchall()
        count = 0
        for row in rows:
            try:
                pg_cursor.execute("""
                    INSERT INTO tracked_wallets
                    (wallet_id, wallet_address, wallet_name, total_tracked_buys, win_rate,
                     avg_gain, tier, notes, date_added)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (wallet_address) DO NOTHING
                """, (row['wallet_id'], row['wallet_address'], row['wallet_name'],
                      row['total_tracked_buys'], row['win_rate'], row['avg_gain'],
                      row['tier'], row['notes'], row['date_added']))
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")
        pg_conn.commit()
        print(f"  ✅ Migrated {count} wallets")

        # Reset sequences to avoid ID conflicts
        print("\n🔧 Resetting sequences...")
        tables = [
            ('calls_received', 'call_id'),
            ('initial_snapshot', 'snapshot_id'),
            ('my_decisions', 'decision_id'),
            ('performance_tracking', 'tracking_id'),
            ('source_performance', 'source_id'),
            ('tracked_wallets', 'wallet_id')
        ]
        for table, id_col in tables:
            try:
                pg_cursor.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', '{id_col}'),
                           COALESCE((SELECT MAX({id_col}) FROM {table}), 0) + 1, false)
                """)
            except Exception as e:
                print(f"  Warning for {table}: {e}")
        pg_conn.commit()
        print("  ✅ Sequences reset")

        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        print("\nYour data is now in Supabase. The cloud tracker will use this database.")

    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate()
