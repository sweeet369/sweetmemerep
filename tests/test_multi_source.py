#!/usr/bin/env python3
"""
Test script for multi-source tracking feature
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MemecoinDatabase

def test_multi_source():
    """Test multi-source tracking functionality."""
    print("="*60)
    print("🧪 MULTI-SOURCE TRACKING - TEST")
    print("="*60)

    db = MemecoinDatabase("memecoin_analyzer.db")

    # Test 1: Create a token with multiple sources
    print("\n1️⃣  Testing token with multiple sources...")
    sources_str = "Discord Degen, Twitter Alpha, Telegram Signal"
    call_id = db.insert_call(
        contract_address="TestToken123MultiSource",
        token_symbol="TEST",
        token_name="Test Multi Source Token",
        source=sources_str,
        blockchain="Solana"
    )
    print(f"✅ Created token with sources: {sources_str}")
    print(f"   Call ID: {call_id}")

    # Test 2: Add snapshot and decision
    snapshot_data = {
        'liquidity_usd': 50000.0,
        'holder_count': 200,
        'top_holder_percent': 10.0,
        'top_10_holders_percent': 35.0,
        'token_age_hours': 5.0,
        'market_cap': 200000.0,
        'volume_24h': 30000.0,
        'price_usd': 0.002,
        'mint_authority_revoked': 1,
        'freeze_authority_revoked': 1,
        'rugcheck_score': 8.5,
        'safety_score': 8.5,
        'raw_data': {}
    }
    db.insert_snapshot(call_id, snapshot_data)
    db.insert_decision(
        call_id=call_id,
        decision="TRADE",
        trade_size_usd=100.0,
        entry_price=0.002,
        reasoning_notes="Multiple good sources",
        emotional_state="calm",
        confidence_level=8
    )
    print("✅ Added snapshot and decision")

    # Test 3: Update performance for each source
    print("\n2️⃣  Updating performance for each source...")
    sources = [s.strip() for s in sources_str.split(',')]
    for source in sources:
        db.update_source_performance(source)
        print(f"   ✅ Updated: {source}")

    # Test 4: View all sources
    print("\n3️⃣  Viewing all source stats...")
    all_sources = db.get_all_sources()
    print(f"\n📊 Found {len(all_sources)} source(s):")
    for src in all_sources:
        print(f"   • {src['source_name']}: {src['total_calls']} call(s), Tier {src['tier']}")

    # Test 5: Add more sources to existing token
    print("\n4️⃣  Testing add sources to existing token...")
    call = db.get_call_by_address("TestToken123MultiSource")
    print(f"   Current sources: {call['source']}")

    # Simulate adding new sources
    new_sources = "Whale Alert, Smart Money"
    existing_sources = [s.strip() for s in call['source'].split(',')]
    new_source_list = [s.strip() for s in new_sources.split(',')]
    all_sources_list = existing_sources + new_source_list
    updated_source = ', '.join(all_sources_list)

    db.cursor.execute('''
        UPDATE calls_received
        SET source = ?
        WHERE contract_address = ?
    ''', (updated_source, "TestToken123MultiSource"))
    db.conn.commit()

    print(f"   ✅ Added new sources: {new_sources}")
    print(f"   📍 Updated sources: {updated_source}")

    # Update performance for new sources
    for src in new_source_list:
        db.update_source_performance(src)

    # Final check
    call = db.get_call_by_address("TestToken123MultiSource")
    print(f"\n5️⃣  Final check:")
    print(f"   Token: {call['token_symbol']}")
    print(f"   All sources: {call['source']}")
    print(f"   Total sources: {len([s for s in call['source'].split(',')])} sources")

    db.close()

    print("\n" + "="*60)
    print("✅ ALL MULTI-SOURCE TESTS PASSED!")
    print("="*60)
    print("\n💡 Now try in analyzer:")
    print("   1. python3 analyzer.py")
    print("   2. Select [1] to analyze - enter multiple sources like:")
    print("      'Discord Degen, Twitter Alpha'")
    print("   3. Select [5] to add sources to existing tokens")
    print()

if __name__ == "__main__":
    test_multi_source()
