#!/usr/bin/env python3
"""
Cleanup Script for Source Performance
Removes combined source entries and recalculates stats for individual sources.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MemecoinDatabase


def main():
    print("="*60)
    print("🧹 SOURCE PERFORMANCE CLEANUP")
    print("="*60)
    print()

    db = MemecoinDatabase()

    # Step 1: Show current combined sources
    print("Step 1: Checking for combined source entries...")
    db.cursor.execute('''
        SELECT source_name, total_calls FROM source_performance
        WHERE source_name LIKE '%,%'
        ORDER BY source_name
    ''')
    combined = db.cursor.fetchall()

    if combined:
        print(f"\n❌ Found {len(combined)} combined source entries:")
        for row in combined:
            print(f"   - {row['source_name']} ({row['total_calls']} calls)")
    else:
        print("✅ No combined source entries found")

    # Step 2: Get all unique sources from calls_received
    print("\nStep 2: Finding all individual sources...")
    db.cursor.execute('SELECT DISTINCT source FROM calls_received')
    all_source_strings = [row['source'] for row in db.cursor.fetchall()]

    # Split all comma-separated sources into individual sources
    individual_sources = set()
    for source_string in all_source_strings:
        for source in source_string.split(','):
            source = source.strip()
            if source:
                individual_sources.add(source)

    print(f"✅ Found {len(individual_sources)} unique individual sources")

    # Step 3: Clean up combined entries
    if combined:
        print("\nStep 3: Removing combined source entries...")
        removed_count = db.cleanup_combined_sources()
        print(f"✅ Removed {removed_count} combined entries")
    else:
        print("\nStep 3: No cleanup needed")

    # Step 4: Rebuild stats for all individual sources
    print("\nStep 4: Rebuilding statistics for all individual sources...")
    for i, source in enumerate(sorted(individual_sources), 1):
        db.update_source_performance(source)
        print(f"  [{i}/{len(individual_sources)}] ✅ {source}")

    # Step 5: Show final results
    print("\n" + "="*60)
    print("📊 FINAL SOURCE STATISTICS")
    print("="*60)

    sources = db.get_all_sources()
    if sources:
        print(f"\n{'Tier':<6} {'Source':<30} {'Calls':<8} {'Traded':<8} {'Win%':<8} {'Avg Gain':<12}")
        print("─"*85)
        for source in sources:
            tier = source['tier']
            name = source['source_name'][:29]
            total = source['total_calls']
            traded = source['calls_traded']
            win_rate = source['win_rate'] * 100
            avg_gain = source['avg_max_gain']

            tier_emoji = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉'}.get(tier, '📊')
            print(f"{tier_emoji} {tier:<4} {name:<30} {total:<8} {traded:<8} {win_rate:>6.1f}% {avg_gain:>10.1f}%")
    else:
        print("\n⚠️  No source statistics available")

    db.close()

    print("\n" + "="*60)
    print("✅ CLEANUP COMPLETE!")
    print("="*60)
    print()


if __name__ == "__main__":
    main()
