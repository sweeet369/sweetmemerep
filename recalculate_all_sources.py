#!/usr/bin/env python3
"""
Recalculate source performance statistics for ALL sources in the database.
This includes sources with closed positions or PASS decisions.
"""

from database import MemecoinDatabase

def main():
    print("="*60)
    print("📊 RECALCULATING ALL SOURCE STATISTICS")
    print("="*60)

    db = MemecoinDatabase()

    # Get all unique sources from calls_received (including comma-separated)
    db.cursor.execute("SELECT DISTINCT source FROM calls_received")
    all_sources_raw = [row['source'] for row in db.cursor.fetchall()]

    # Split comma-separated sources and create a unique set
    all_sources = set()
    for source_str in all_sources_raw:
        if source_str:
            # Split by comma and strip whitespace
            sources = [s.strip() for s in source_str.split(',') if s.strip()]
            all_sources.update(sources)

    print(f"\n📋 Found {len(all_sources)} unique source(s) in database")

    if not all_sources:
        print("\n⚠️  No sources found in database!")
        db.close()
        return

    print("\n🔄 Recalculating statistics for all sources...\n")

    # Update each source
    for i, source in enumerate(sorted(all_sources), 1):
        print(f"[{i}/{len(all_sources)}] {source}")
        db.update_source_performance(source)

    db.close()

    print("\n" + "="*60)
    print("✅ All source statistics recalculated!")
    print("="*60)
    print("\n💡 You can now view stats with: python3 analyzer.py")
    print("   Select option [2] to see all sources.")

if __name__ == "__main__":
    main()
