#!/usr/bin/env python3
"""
Add hit_rate column to source_performance table
"""

import sqlite3
import os


def main():
    db_path = '/Users/shecksaad/Desktop/sweetmemerep/memecoin_analyzer.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return

    print("="*70)
    print("🔧 ADDING HIT_RATE COLUMN TO SOURCE_PERFORMANCE")
    print("="*70)
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(source_performance)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'hit_rate' in columns:
        print("⏭️  Column 'hit_rate' already exists")
    else:
        cursor.execute('ALTER TABLE source_performance ADD COLUMN hit_rate REAL DEFAULT 0.0')
        conn.commit()
        print("✅ Added column: hit_rate (REAL DEFAULT 0.0)")

    conn.close()

    print()
    print("="*70)
    print("✅ MIGRATION COMPLETE!")
    print("="*70)
    print()
    print("Next: Run cleanup_sources.py to recalculate all source stats")


if __name__ == "__main__":
    main()
