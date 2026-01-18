#!/usr/bin/env python3
"""
Add multi-pool liquidity tracking columns to initial_snapshot table
"""

import sqlite3
import os


def main():
    db_path = '/Users/shecksaad/Desktop/sweetmemerep/memecoin_analyzer.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return

    print("="*70)
    print("🔧 ADDING MULTI-POOL LIQUIDITY COLUMNS")
    print("="*70)
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(initial_snapshot)")
    columns = [row[1] for row in cursor.fetchall()]

    migrations = [
        ('main_pool_liquidity', 'REAL'),
        ('total_liquidity', 'REAL'),
        ('main_pool_dex', 'TEXT')
    ]

    added = 0
    for col_name, col_type in migrations:
        if col_name in columns:
            print(f"⏭️  Column '{col_name}' already exists")
        else:
            cursor.execute(f'ALTER TABLE initial_snapshot ADD COLUMN {col_name} {col_type}')
            print(f"✅ Added column: {col_name} ({col_type})")
            added += 1

    conn.commit()
    conn.close()

    print()
    print("="*70)
    print(f"✅ MIGRATION COMPLETE! {added} column(s) added")
    print("="*70)
    print()
    if added > 0:
        print("New columns track multi-pool liquidity:")
        print("  • main_pool_liquidity - Highest liquidity pool")
        print("  • total_liquidity - Sum of all pools")
        print("  • main_pool_dex - DEX name (Raydium/Orca/etc)")


if __name__ == "__main__":
    main()
