#!/usr/bin/env python3
"""
Fix Gain Cap Script
Caps all max_gain_observed and max_loss_observed values at -100% minimum.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MemecoinDatabase


def main():
    print("="*60)
    print("🔧 FIX GAIN CAP - CAP AT -100% MINIMUM")
    print("="*60)
    print()

    db = MemecoinDatabase()

    # Find all records with gains/losses below -100%
    print("Step 1: Finding records with impossible values (< -100%)...")
    db.cursor.execute('''
        SELECT
            call_id,
            max_gain_observed,
            max_loss_observed
        FROM performance_tracking
        WHERE max_gain_observed < -100 OR max_loss_observed < -100
    ''')

    bad_records = db.cursor.fetchall()

    if not bad_records:
        print("✅ No records found with values below -100%")
        db.close()
        return

    print(f"❌ Found {len(bad_records)} records with impossible values:\n")

    for record in bad_records:
        call_id = record['call_id']
        max_gain = record['max_gain_observed']
        max_loss = record['max_loss_observed']

        # Get token symbol for display
        db.cursor.execute('SELECT token_symbol FROM calls_received WHERE call_id = ?', (call_id,))
        token = db.cursor.fetchone()
        symbol = token['token_symbol'] if token else 'Unknown'

        print(f"  Token: {symbol}")
        if max_gain and max_gain < -100:
            print(f"    Max Gain: {max_gain:.2f}% ❌")
        if max_loss and max_loss < -100:
            print(f"    Max Loss: {max_loss:.2f}% ❌")
        print()

    # Fix all records
    print("Step 2: Fixing all records...")

    # Cap max_gain_observed at -100%
    db.cursor.execute('''
        UPDATE performance_tracking
        SET max_gain_observed = -100.0
        WHERE max_gain_observed < -100
    ''')
    gain_fixed = db.cursor.rowcount

    # Cap max_loss_observed at -100%
    db.cursor.execute('''
        UPDATE performance_tracking
        SET max_loss_observed = -100.0
        WHERE max_loss_observed < -100
    ''')
    loss_fixed = db.cursor.rowcount

    db.conn.commit()

    print(f"✅ Fixed {gain_fixed} max_gain_observed records")
    print(f"✅ Fixed {loss_fixed} max_loss_observed records")

    # Recalculate source performance with fixed values
    print("\nStep 3: Recalculating source performance stats...")

    # Get all unique sources
    db.cursor.execute('SELECT DISTINCT source FROM calls_received')
    all_source_strings = [row['source'] for row in db.cursor.fetchall()]

    # Split comma-separated sources
    individual_sources = set()
    for source_string in all_source_strings:
        for source in source_string.split(','):
            source = source.strip()
            if source:
                individual_sources.add(source)

    # Update each source
    for i, source in enumerate(sorted(individual_sources), 1):
        db.update_source_performance(source)
        print(f"  [{i}/{len(individual_sources)}] ✅ {source}")

    # Verify fix
    print("\nStep 4: Verifying fix...")
    db.cursor.execute('''
        SELECT COUNT(*) as count
        FROM performance_tracking
        WHERE max_gain_observed < -100 OR max_loss_observed < -100
    ''')

    remaining = db.cursor.fetchone()['count']

    if remaining == 0:
        print("✅ All records fixed! No values below -100% remaining.")
    else:
        print(f"⚠️  {remaining} records still have issues")

    db.close()

    print("\n" + "="*60)
    print("✅ FIX COMPLETE!")
    print("="*60)
    print()


if __name__ == "__main__":
    main()
