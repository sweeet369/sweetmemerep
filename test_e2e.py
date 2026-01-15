#!/usr/bin/env python3
"""
End-to-end test of the memecoin analyzer system
"""

from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher

def test_full_workflow():
    """Test the complete workflow."""
    print("="*60)
    print("🧪 END-TO-END TEST")
    print("="*60)

    # Initialize components
    print("\n1️⃣  Initializing database and fetcher...")
    db = MemecoinDatabase("test_e2e.db")
    fetcher = MemecoinDataFetcher()
    print("✅ Components initialized")

    # Test with BONK token
    test_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    test_source = "Test Alpha Group"

    # Fetch data
    print(f"\n2️⃣  Fetching data for BONK token...")
    data = fetcher.fetch_all_data(test_address)

    if not data:
        print("❌ Failed to fetch data")
        return False

    print("✅ Data fetched successfully")

    # Get token info
    token_name = "BONK"
    token_symbol = "BONK"
    if data.get('raw_data', {}).get('dexscreener'):
        dex_raw = data['raw_data']['dexscreener']
        token_name = dex_raw.get('baseToken', {}).get('name', 'BONK')
        token_symbol = dex_raw.get('baseToken', {}).get('symbol', 'BONK')

    # Insert call
    print(f"\n3️⃣  Inserting call to database...")
    call_id = db.insert_call(
        contract_address=test_address,
        token_symbol=token_symbol,
        token_name=token_name,
        source=test_source,
        blockchain="Solana"
    )
    print(f"✅ Call inserted with ID: {call_id}")

    # Insert snapshot
    print(f"\n4️⃣  Inserting snapshot data...")
    snapshot_id = db.insert_snapshot(call_id, data)
    print(f"✅ Snapshot inserted with ID: {snapshot_id}")

    # Insert decision
    print(f"\n5️⃣  Recording trading decision...")
    decision_id = db.insert_decision(
        call_id=call_id,
        decision="TRADE",
        trade_size_usd=100.0,
        entry_price=data.get('price_usd'),
        reasoning_notes="Test trade - good safety score",
        emotional_state="calm",
        confidence_level=8
    )
    print(f"✅ Decision recorded with ID: {decision_id}")

    # Update source performance
    print(f"\n6️⃣  Updating source performance...")
    db.update_source_performance(test_source)
    print(f"✅ Source performance updated")

    # Retrieve and display source stats
    print(f"\n7️⃣  Retrieving source statistics...")
    sources = db.get_all_sources()
    print(f"✅ Found {len(sources)} source(s)")

    if sources:
        source = sources[0]
        print(f"\n📊 Source: {source['source_name']}")
        print(f"   Tier: {source['tier']}")
        print(f"   Total Calls: {source['total_calls']}")
        print(f"   Calls Traded: {source['calls_traded']}")

    # Display key data
    print(f"\n8️⃣  Analysis Summary:")
    print(f"   💧 Liquidity: ${data.get('liquidity_usd', 0):,.2f}")
    print(f"   🎯 Safety Score: {data.get('safety_score', 0):.1f}/10")
    print(f"   ✅ Mint Revoked: {bool(data.get('mint_authority_revoked'))}")
    print(f"   ✅ Freeze Revoked: {bool(data.get('freeze_authority_revoked'))}")

    # Clean up
    db.close()

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    return True


if __name__ == "__main__":
    try:
        success = test_full_workflow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
