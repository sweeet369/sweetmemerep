#!/usr/bin/env python3
"""
Migration script: Add advanced analytics columns to existing databases.

Adds new columns to:
- performance_tracking: 15m/30m prices, time_to_max_gain, time_to_rug, max_gain_timestamp
- initial_snapshot: volume_liquidity_ratio, buy_sell_ratio, momentum_score, sol_price_usd
- source_performance: avg_time_to_max_gain_hours, median_max_gain, baseline_alpha,
                      confidence_score, recent_hit_rate, sample_size

Safe to run multiple times — uses IF NOT EXISTS / try-except patterns.
Works for both SQLite and PostgreSQL.
"""

import sys
import os

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MemecoinDatabase


# Column definitions: (table, column_name, column_type)
NEW_COLUMNS = [
    # performance_tracking
    ("performance_tracking", "price_15m_later", "REAL"),
    ("performance_tracking", "price_30m_later", "REAL"),
    ("performance_tracking", "time_to_max_gain_hours", "REAL"),
    ("performance_tracking", "time_to_rug_hours", "REAL"),
    ("performance_tracking", "max_gain_timestamp", "TEXT"),

    # initial_snapshot
    ("initial_snapshot", "volume_liquidity_ratio", "REAL"),
    ("initial_snapshot", "buy_sell_ratio", "REAL"),
    ("initial_snapshot", "momentum_score", "REAL"),
    ("initial_snapshot", "sol_price_usd", "REAL"),

    # source_performance
    ("source_performance", "avg_time_to_max_gain_hours", "REAL"),
    ("source_performance", "median_max_gain", "REAL"),
    ("source_performance", "baseline_alpha", "REAL"),
    ("source_performance", "confidence_score", "REAL"),
    ("source_performance", "recent_hit_rate", "REAL"),
    ("source_performance", "sample_size", "INTEGER DEFAULT 0"),
]


def run_migration():
    """Run the migration to add all new analytics columns."""
    print("=" * 60)
    print("MIGRATION: Add Advanced Analytics Columns")
    print("=" * 60)

    db = MemecoinDatabase()
    print(f"\nConnected to: {db.db_type}")
    print(f"Database: {db.db_path}")

    added = 0
    skipped = 0
    errors = 0

    for table, column, col_type in NEW_COLUMNS:
        try:
            if db.db_type == 'postgres':
                # PostgreSQL: use IF NOT EXISTS (available in PG 9.6+)
                # Map SQLite types to PostgreSQL types
                pg_type = col_type
                if col_type == "REAL":
                    pg_type = "DOUBLE PRECISION"
                elif col_type == "INTEGER DEFAULT 0":
                    pg_type = "INTEGER DEFAULT 0"

                db.cursor.execute(f"""
                    DO $$
                    BEGIN
                        ALTER TABLE {table} ADD COLUMN {column} {pg_type};
                    EXCEPTION
                        WHEN duplicate_column THEN
                            NULL;
                    END $$;
                """)
            else:
                # SQLite: try ALTER TABLE, catch error if column exists
                db.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

            db.conn.commit()
            print(f"  + Added {table}.{column} ({col_type})")
            added += 1

        except Exception as e:
            error_str = str(e).lower()
            if 'duplicate' in error_str or 'already exists' in error_str:
                print(f"  - Skipped {table}.{column} (already exists)")
                skipped += 1
            else:
                print(f"  ! Error adding {table}.{column}: {e}")
                errors += 1
            # Rollback any failed transaction
            try:
                db.conn.rollback()
            except Exception:
                pass

    print(f"\nResults: {added} added, {skipped} skipped, {errors} errors")

    db.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    run_migration()
