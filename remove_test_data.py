#!/usr/bin/env python3
"""
Remove test/fake tokens from the database
"""

from database import MemecoinDatabase


def main():
    print("="*80)
    print("🧹 REMOVING TEST/FAKE TOKEN DATA")
    print("="*80)
    print()

    db = MemecoinDatabase()

    # List of test tokens to remove (add more as needed)
    test_tokens = ['TEST', 'SCAM', 'PEPE', 'BONK']

    print("Test tokens to remove:")
    for token in test_tokens:
        print(f"  - {token}")
    print()

    # Check how many calls will be affected
    placeholders = ','.join('?' * len(test_tokens))
    db.cursor.execute(f'''
        SELECT COUNT(*) as count
        FROM calls_received
        WHERE token_symbol IN ({placeholders})
    ''', test_tokens)

    count = db.cursor.fetchone()['count']
    print(f"Found {count} test token calls to remove")
    print()

    if count == 0:
        print("✅ No test tokens found - database is clean!")
        db.close()
        return

    # Show details
    print("Details:")
    db.cursor.execute(f'''
        SELECT
            c.call_id,
            c.token_symbol,
            c.source,
            p.max_gain_observed
        FROM calls_received c
        LEFT JOIN performance_tracking p ON c.call_id = p.call_id
        WHERE c.token_symbol IN ({placeholders})
    ''', test_tokens)

    rows = db.cursor.fetchall()
    for row in rows:
        gain = row['max_gain_observed'] if row['max_gain_observed'] else "N/A"
        print(f"  Call ID {row['call_id']}: {row['token_symbol']} from {row['source']} (gain: {gain}%)")
    print()

    # Ask for confirmation
    response = input("⚠️  Delete these test tokens? [yes/NO]: ").strip().lower()

    if response != 'yes':
        print("❌ Cancelled - no changes made")
        db.close()
        return

    # Delete from all related tables
    for token in test_tokens:
        # Get call IDs for this token
        db.cursor.execute('''
            SELECT call_id FROM calls_received
            WHERE token_symbol = ?
        ''', (token,))

        call_ids = [row['call_id'] for row in db.cursor.fetchall()]

        if call_ids:
            placeholders = ','.join('?' * len(call_ids))

            # Delete from performance_tracking
            db.cursor.execute(f'''
                DELETE FROM performance_tracking
                WHERE call_id IN ({placeholders})
            ''', call_ids)
            print(f"  ✅ Removed performance tracking for {token}")

            # Delete from initial_snapshot
            db.cursor.execute(f'''
                DELETE FROM initial_snapshot
                WHERE call_id IN ({placeholders})
            ''', call_ids)
            print(f"  ✅ Removed initial snapshot for {token}")

            # Delete from my_decisions
            db.cursor.execute(f'''
                DELETE FROM my_decisions
                WHERE call_id IN ({placeholders})
            ''', call_ids)
            print(f"  ✅ Removed decisions for {token}")

            # Delete from calls_received
            db.cursor.execute('''
                DELETE FROM calls_received
                WHERE token_symbol = ?
            ''', (token,))
            print(f"  ✅ Removed call record for {token}")

    db.conn.commit()
    print()
    print("✅ Test tokens removed successfully!")
    print()
    print("Now recalculating source performance...")

    # Recalculate source performance for all remaining sources
    db.cursor.execute('SELECT DISTINCT source FROM calls_received')
    sources_raw = db.cursor.fetchall()

    # Parse all individual sources from comma-separated lists
    all_sources = set()
    for row in sources_raw:
        source_list = [s.strip() for s in row['source'].split(',') if s.strip()]
        all_sources.update(source_list)

    # Recalculate for each source
    for source in sorted(all_sources):
        db.update_source_performance(source)
        print(f"  ✅ Recalculated: {source}")

    # Remove orphaned source_performance entries
    db.cursor.execute('''
        DELETE FROM source_performance
        WHERE source_name NOT IN (
            SELECT DISTINCT source FROM calls_received
            UNION
            SELECT DISTINCT TRIM(value) FROM (
                SELECT TRIM(SUBSTR(source, instr(',' || source, ',') + 1)) as value
                FROM calls_received
                WHERE source LIKE '%,%'
            )
        )
    ''')

    db.conn.commit()
    db.close()

    print()
    print("="*80)
    print("✅ CLEANUP COMPLETE!")
    print("="*80)
    print()
    print("Run analyzer.py now to see clean source stats!")


if __name__ == "__main__":
    main()
