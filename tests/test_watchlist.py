#!/usr/bin/env python3
"""
Test watchlist feature with sample data
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher
from datetime import datetime, timedelta

def setup_watchlist_demo():
    """Create sample watchlist data for testing."""
    print("Setting up watchlist demo data...")

    db = MemecoinDatabase("memecoin_analyzer.db")
    fetcher = MemecoinDataFetcher()

    # Add a real token to watchlist
    bonk_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

    print(f"\nFetching BONK token data...")
    data = fetcher.fetch_all_data(bonk_address)

    if not data:
        print("❌ Failed to fetch data")
        return

    # Get token info
    token_name = "Bonk"
    token_symbol = "BONK"
    if data.get('raw_data', {}).get('dexscreener'):
        dex_raw = data['raw_data']['dexscreener']
        token_name = dex_raw.get('baseToken', {}).get('name', 'Bonk')
        token_symbol = dex_raw.get('baseToken', {}).get('symbol', 'BONK')

    # Insert call
    call_id = db.insert_call(
        contract_address=bonk_address,
        token_symbol=token_symbol,
        token_name=token_name,
        source="Demo Watchlist Source",
        blockchain="Solana"
    )
    print(f"✅ Added {token_symbol} to database (Call ID: {call_id})")

    # Insert snapshot
    db.insert_snapshot(call_id, data)
    print(f"✅ Snapshot saved")

    # Insert WATCH decision
    db.insert_decision(
        call_id=call_id,
        decision="WATCH",
        trade_size_usd=None,
        entry_price=data.get('price_usd'),
        reasoning_notes="Demo token - watching for good entry point",
        emotional_state="calm",
        confidence_level=7
    )
    print(f"✅ Added to WATCHLIST")

    # Add some performance data
    db.insert_or_update_performance(call_id, {
        'max_gain_observed': 5.5,
        'max_loss_observed': -2.1,
        'token_still_alive': 'yes',
        'rug_pull_occurred': 'no'
    })
    print(f"✅ Performance data added")

    db.close()

    print("\n" + "="*60)
    print("✅ Watchlist demo data created!")
    print("="*60)
    print("\nNow run: python3 analyzer.py")
    print("Select option [3] to view your watchlist!")
    print()

if __name__ == "__main__":
    setup_watchlist_demo()
