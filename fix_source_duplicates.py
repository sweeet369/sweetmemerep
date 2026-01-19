#!/usr/bin/env python3
"""
Fix duplicate sources caused by case sensitivity.
Normalizes all source names to lowercase.
"""

import sqlite3
import os

# Get database path (use relative path)
db_path = os.path.join(os.path.dirname(__file__), 'memecoin_analyzer.db')

def main():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("="*60)
    print("🔧 FIXING SOURCE NAME DUPLICATES")
    print("="*60)

    # Get all unique sources
    cursor.execute("SELECT DISTINCT source FROM calls_received")
    sources = [row[0] for row in cursor.fetchall()]

    print(f"\n📋 Found {len(sources)} unique source entries")

    # Find sources that need normalization
    updates_needed = []
    for source in sources:
        if source and source != source.lower():
            updates_needed.append((source, source.lower()))
            print(f"   ❌ '{source}' → '{source.lower()}'")

    if not updates_needed:
        print("\n✅ All sources are already lowercase!")
        conn.close()
        return

    print(f"\n🔄 Normalizing {len(updates_needed)} source(s)...")

    # Update calls_received table
    for old_source, new_source in updates_needed:
        cursor.execute('''
            UPDATE calls_received
            SET source = ?
            WHERE source = ?
        ''', (new_source, old_source))
        print(f"   ✅ Updated calls: '{old_source}' → '{new_source}'")

    # Clean up source_performance table (delete old entries, they'll be recalculated)
    for old_source, new_source in updates_needed:
        cursor.execute('''
            DELETE FROM source_performance
            WHERE source_name = ?
        ''', (old_source,))
        print(f"   🗑️  Removed old stats for: '{old_source}'")

    conn.commit()
    conn.close()

    print("\n" + "="*60)
    print("✅ Source names normalized!")
    print("="*60)
    print("\n💡 Now run: python3 performance_tracker.py")
    print("   This will recalculate stats for all sources.")

if __name__ == "__main__":
    main()
