#!/usr/bin/env python3
"""
Test script for smart money wallet tracking feature
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MemecoinDatabase

def setup_demo_wallets():
    """Set up demo smart money wallets for testing."""
    print("="*60)
    print("🧪 SMART MONEY TRACKING - DEMO SETUP")
    print("="*60)

    db = MemecoinDatabase("memecoin_analyzer.db")

    # Add some demo smart money wallets
    wallets = [
        {
            'address': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
            'name': 'Elite Trader 1',
            'notes': 'Consistently profitable trader'
        },
        {
            'address': 'GrWRS3YZvFmCmjsHDTvF6YHU1B8GFtLB1MXjSKdq7qk',
            'name': 'Degen King',
            'notes': 'High risk, high reward'
        },
        {
            'address': 'CwCe6AcQFq7AiVNUxTGYPMmQEbqfGKYCx5S5VqVG5Dpv',
            'name': 'Whale Watcher',
            'notes': 'Follows whale movements'
        }
    ]

    print("\n➕ Adding demo smart money wallets...")
    for wallet in wallets:
        wallet_id = db.insert_wallet(
            wallet_address=wallet['address'],
            wallet_name=wallet['name'],
            notes=wallet['notes']
        )
        if wallet_id > 0:
            print(f"   ✅ Added: {wallet['name']}")
        else:
            print(f"   ⚠️  Wallet already exists: {wallet['name']}")

    # Update their performance stats
    print("\n📊 Updating performance stats...")
    db.update_wallet_performance('7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU', 0.78, 450, 25)
    db.update_wallet_performance('GrWRS3YZvFmCmjsHDTvF6YHU1B8GFtLB1MXjSKdq7qk', 0.65, 280, 18)
    db.update_wallet_performance('CwCe6AcQFq7AiVNUxTGYPMmQEbqfGKYCx5S5VqVG5Dpv', 0.55, 150, 12)
    print("   ✅ Performance stats updated")

    # Display all wallets
    print("\n💰 TRACKED SMART MONEY WALLETS:")
    print("─"*60)
    wallets = db.get_all_wallets()

    for wallet in wallets:
        tier = wallet['tier']
        tier_emoji = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉'}.get(tier, '📊')
        name = wallet['wallet_name']
        win_rate = wallet['win_rate'] * 100
        avg_gain = wallet['avg_gain']

        print(f"{tier_emoji} {tier}-Tier: {name}")
        print(f"   Win Rate: {win_rate:.0f}% | Avg Gain: +{avg_gain:.0f}%")

    db.close()

    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\n📋 Next steps:")
    print("   1. Run: python3 analyzer.py")
    print("   2. Select [4] Manage tracked wallets → [3] View all wallets")
    print("   3. Analyze a token - if any tracked wallets are top holders,")
    print("      you'll see 💰 SMART MONEY DETECTED section!")
    print("\n💡 Note: Smart money detection only works when:")
    print("   - RugCheck API returns top holder wallet addresses")
    print("   - Those addresses match wallets in your tracked list")
    print()

if __name__ == "__main__":
    setup_demo_wallets()
