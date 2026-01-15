#!/usr/bin/env python3
"""
Manually create watchlist demo data (without API calls)
"""

from database import MemecoinDatabase
from datetime import datetime

def setup_watchlist_demo():
    """Create sample watchlist data for testing."""
    print("Setting up watchlist demo data (manual)...")

    db = MemecoinDatabase("memecoin_analyzer.db")

    # Sample token 1
    call_id_1 = db.insert_call(
        contract_address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        token_symbol="BONK",
        token_name="Bonk",
        source="Alpha Calls",
        blockchain="Solana"
    )

    snapshot_data_1 = {
        'liquidity_usd': 1500000.0,
        'holder_count': 2000,
        'top_holder_percent': 8.5,
        'top_10_holders_percent': 35.0,
        'token_age_hours': 720.0,
        'market_cap': 900000000.0,
        'volume_24h': 250000.0,
        'price_usd': 0.0000105,
        'mint_authority_revoked': 1,
        'freeze_authority_revoked': 1,
        'rugcheck_score': 9.5,
        'safety_score': 9.5,
        'raw_data': {}
    }
    db.insert_snapshot(call_id_1, snapshot_data_1)
    db.insert_decision(
        call_id=call_id_1,
        decision="WATCH",
        trade_size_usd=None,
        entry_price=0.0000105,
        reasoning_notes="Established token, waiting for dip to enter",
        emotional_state="calm",
        confidence_level=8
    )
    db.insert_or_update_performance(call_id_1, {
        'max_gain_observed': 12.5,
        'max_loss_observed': -3.2,
        'token_still_alive': 'yes',
        'rug_pull_occurred': 'no'
    })
    print(f"✅ Added BONK to watchlist")

    # Sample token 2 - pumping hard
    call_id_2 = db.insert_call(
        contract_address="4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        token_symbol="PEPE",
        token_name="Pepe Coin",
        source="Discord Degen",
        blockchain="Solana"
    )

    snapshot_data_2 = {
        'liquidity_usd': 85000.0,
        'holder_count': 450,
        'top_holder_percent': 12.0,
        'top_10_holders_percent': 42.0,
        'token_age_hours': 48.0,
        'market_cap': 500000.0,
        'volume_24h': 125000.0,
        'price_usd': 0.00025,
        'mint_authority_revoked': 1,
        'freeze_authority_revoked': 1,
        'rugcheck_score': 7.5,
        'safety_score': 8.0,
        'raw_data': {}
    }
    db.insert_snapshot(call_id_2, snapshot_data_2)
    db.insert_decision(
        call_id=call_id_2,
        decision="WATCH",
        trade_size_usd=None,
        entry_price=0.00025,
        reasoning_notes="New token, good early metrics but want to see stability",
        emotional_state="fomo",
        confidence_level=6
    )
    db.insert_or_update_performance(call_id_2, {
        'max_gain_observed': 185.0,  # 185% gain!
        'max_loss_observed': -8.0,
        'token_still_alive': 'yes',
        'rug_pull_occurred': 'no'
    })
    print(f"✅ Added PEPE to watchlist (pumping!)")

    # Sample token 3 - rugged
    call_id_3 = db.insert_call(
        contract_address="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        token_symbol="SCAM",
        token_name="Definitely Not A Scam",
        source="Random Twitter",
        blockchain="Solana"
    )

    snapshot_data_3 = {
        'liquidity_usd': 15000.0,
        'holder_count': 120,
        'top_holder_percent': 25.0,
        'top_10_holders_percent': 68.0,
        'token_age_hours': 2.0,
        'market_cap': 50000.0,
        'volume_24h': 8000.0,
        'price_usd': 0.001,
        'mint_authority_revoked': 0,
        'freeze_authority_revoked': 0,
        'rugcheck_score': 3.0,
        'safety_score': 2.5,
        'raw_data': {}
    }
    db.insert_snapshot(call_id_3, snapshot_data_3)
    db.insert_decision(
        call_id=call_id_3,
        decision="WATCH",
        trade_size_usd=None,
        entry_price=0.001,
        reasoning_notes="Red flags but volume is interesting, watching carefully",
        emotional_state="uncertain",
        confidence_level=3
    )
    db.insert_or_update_performance(call_id_3, {
        'max_gain_observed': 45.0,
        'max_loss_observed': -99.8,
        'token_still_alive': 'no',
        'rug_pull_occurred': 'yes'
    })
    print(f"✅ Added SCAM to watchlist (rugged as expected)")

    # Update source performance
    db.update_source_performance("Alpha Calls")
    db.update_source_performance("Discord Degen")
    db.update_source_performance("Random Twitter")

    db.close()

    print("\n" + "="*60)
    print("✅ Watchlist demo data created!")
    print("="*60)
    print("\n📋 Added 3 tokens to watchlist:")
    print("   1. BONK - Stable, small gain")
    print("   2. PEPE - MAJOR PUMP (+185%!)")
    print("   3. SCAM - Rugged (-99.8%)")
    print("\nNow run: python3 analyzer.py")
    print("Select option [3] to view your watchlist!")
    print()

if __name__ == "__main__":
    setup_watchlist_demo()
