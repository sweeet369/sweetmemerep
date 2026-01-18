#!/usr/bin/env python3
"""
Add entry_timestamp column to my_decisions table for proper entry tracking
"""

import sqlite3
import os


def main():
    db_path = '/Users/shecksaad/Desktop/sweetmemerep/memecoin_analyzer.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return

    print("="*70)
    print("🔧 ADDING ENTRY_TIMESTAMP COLUMN")
    print("="*70)
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(my_decisions)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'entry_timestamp' in columns:
        print("⏭️  Column 'entry_timestamp' already exists")
    else:
        # Add entry_timestamp column
        cursor.execute('ALTER TABLE my_decisions ADD COLUMN entry_timestamp TEXT')
        print("✅ Added column: entry_timestamp (TEXT)")

        # For existing TRADE decisions, set entry_timestamp = timestamp_decision
        cursor.execute('''
            UPDATE my_decisions
            SET entry_timestamp = timestamp_decision
            WHERE my_decision = 'TRADE' AND entry_timestamp IS NULL
        ''')

        updated = cursor.rowcount
        if updated > 0:
            print(f"✅ Updated {updated} existing TRADE decisions with entry_timestamp")

    conn.commit()
    conn.close()

    print()
    print("="*70)
    print("✅ MIGRATION COMPLETE!")
    print("="*70)
    print()
    print("Price tracking now distinguishes:")
    print("  • Call Price (initial_snapshot.price_usd) - When token first analyzed")
    print("  • Entry Price (my_decisions.entry_price) - When TRADE decision made")
    print("  • Exit Price (my_decisions.actual_exit_price) - When position closed")


if __name__ == "__main__":
    main()
