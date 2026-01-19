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

    # Step 1: Fix calls_received table
    print("\n📋 Step 1: Checking calls_received table...")
    cursor.execute("SELECT DISTINCT source FROM calls_received")
    sources = [row[0] for row in cursor.fetchall()]

    print(f"   Found {len(sources)} unique source entries")

    # Find sources that need normalization
    calls_updates_needed = []
    for source in sources:
        if source and source != source.lower():
            calls_updates_needed.append((source, source.lower()))
            print(f"   ❌ '{source}' → '{source.lower()}'")

    if calls_updates_needed:
        print(f"\n🔄 Normalizing {len(calls_updates_needed)} source(s) in calls_received...")
        for old_source, new_source in calls_updates_needed:
            cursor.execute('''
                UPDATE calls_received
                SET source = ?
                WHERE source = ?
            ''', (new_source, old_source))
            print(f"   ✅ Updated calls: '{old_source}' → '{new_source}'")
    else:
        print("   ✅ All sources in calls_received are already lowercase!")

    # Step 2: Fix source_performance table - check for case-sensitive duplicates
    print("\n📋 Step 2: Checking source_performance table for duplicates...")
    cursor.execute("SELECT DISTINCT source_name FROM source_performance")
    perf_sources = [row[0] for row in cursor.fetchall()]

    print(f"   Found {len(perf_sources)} unique source entries")

    # Group sources by their lowercase version to find duplicates
    lowercase_groups = {}
    for source in perf_sources:
        if source:
            lower = source.lower()
            if lower not in lowercase_groups:
                lowercase_groups[lower] = []
            lowercase_groups[lower].append(source)

    # Find groups with multiple case variations
    duplicates_found = []
    for lower, variants in lowercase_groups.items():
        if len(variants) > 1:
            duplicates_found.append((lower, variants))
            print(f"   ❌ Duplicate: {variants} → '{lower}'")

    if duplicates_found:
        print(f"\n🔄 Cleaning up {len(duplicates_found)} duplicate source(s)...")
        for lower, variants in duplicates_found:
            # Delete ALL variants from source_performance
            for variant in variants:
                cursor.execute('''
                    DELETE FROM source_performance
                    WHERE source_name = ?
                ''', (variant,))
                print(f"   🗑️  Removed: '{variant}'")
    else:
        # Still check for uppercase entries even if not duplicates
        uppercase_found = []
        for source in perf_sources:
            if source and source != source.lower():
                uppercase_found.append(source)
                print(f"   ❌ Uppercase entry: '{source}' → '{source.lower()}'")

        if uppercase_found:
            print(f"\n🔄 Cleaning up {len(uppercase_found)} uppercase source(s)...")
            for source in uppercase_found:
                cursor.execute('''
                    DELETE FROM source_performance
                    WHERE source_name = ?
                ''', (source,))
                print(f"   🗑️  Removed: '{source}'")
        else:
            print("   ✅ No duplicates or uppercase entries in source_performance!")

    conn.commit()
    conn.close()

    print("\n" + "="*60)
    print("✅ Source names normalized!")
    print("="*60)
    print("\n💡 Now run: python3 performance_tracker.py")
    print("   This will recalculate stats for all sources.")

if __name__ == "__main__":
    main()
