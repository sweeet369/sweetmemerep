#!/usr/bin/env python3
"""
Performance Tracker - Automatically updates token performance data

Run this script periodically (via cron or manually) to track token performance over time.
It will fetch current prices and update the performance_tracking table.
"""

import time
from datetime import datetime, timedelta
from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher
from app_logger import tracker_logger, log_performance


class PerformanceTracker:
    """Tracks token performance over time."""

    def __init__(self):
        """Initialize tracker with database and fetcher."""
        self.db = MemecoinDatabase()
        self.fetcher = MemecoinDataFetcher()

    def get_all_tracked_tokens(self):
        """Get all tokens that need performance tracking (WATCH or open TRADE positions only)."""
        self.db.cursor.execute('''
            SELECT
                c.call_id,
                c.contract_address,
                c.token_symbol,
                c.token_name,
                c.source,
                c.blockchain,
                s.snapshot_timestamp,
                s.price_usd as call_price,
                d.my_decision,
                d.entry_price as trade_entry_price,
                d.actual_exit_price
            FROM calls_received c
            JOIN initial_snapshot s ON c.call_id = s.call_id
            JOIN my_decisions d ON c.call_id = d.call_id
            WHERE (
                d.my_decision = 'WATCH'
                OR (d.my_decision = 'TRADE' AND (d.actual_exit_price IS NULL OR d.actual_exit_price = 0))
            )
            ORDER BY s.snapshot_timestamp DESC
        ''')
        return [dict(row) for row in self.db.cursor.fetchall()]

    def calculate_time_since_snapshot(self, snapshot_timestamp):
        """Calculate hours since snapshot was taken."""
        if isinstance(snapshot_timestamp, datetime):
            snapshot_time = snapshot_timestamp
        else:
            snapshot_time = datetime.fromisoformat(str(snapshot_timestamp))
        if snapshot_time.tzinfo is not None:
            snapshot_time = snapshot_time.replace(tzinfo=None)
        now = datetime.now()
        delta = now - snapshot_time
        return delta.total_seconds() / 3600  # hours

    def fetch_current_price(self, address: str, blockchain: str):
        """Fetch current price and market cap for a token (Birdeye)."""
        try:
            data = self.fetcher.fetch_birdeye_data(address, blockchain=blockchain)
            if data:
                return {
                    'price': data.get('price_usd'),
                    'liquidity': data.get('liquidity_usd'),
                    'total_liquidity': data.get('total_liquidity') or data.get('liquidity_usd'),
                    'market_cap': data.get('market_cap'),
                    'exists': True
                }
            else:
                return {'price': None, 'liquidity': None, 'total_liquidity': None, 'market_cap': None, 'exists': None}
        except Exception as e:
            print(f"⚠️  Error fetching price: {e}")
            return {'price': None, 'liquidity': None, 'total_liquidity': None, 'market_cap': None, 'exists': None}

    def calculate_gain_loss(self, entry_price: float, current_price: float):
        """Calculate percentage gain/loss."""
        if not entry_price or not current_price:
            return None
        return ((current_price - entry_price) / entry_price) * 100

    def update_token_performance(self, call_id: int, contract_address: str,
                                entry_price: float, snapshot_timestamp: str,
                                decision_status: str, blockchain: str):
        """Update performance data for a single token."""
        hours_since = self.calculate_time_since_snapshot(snapshot_timestamp)
        minutes_since = hours_since * 60

        # Fetch current price
        print(f"  Checking {contract_address}...")
        current_data = self.fetch_current_price(contract_address, blockchain)

        if current_data['exists'] is False:
            print(f"  ❌ Token no longer exists or not found")
            self.db.insert_or_update_performance(call_id, {
                'token_still_alive': 'no',
                'rug_pull_occurred': 'yes'
            })
            self.db.insert_performance_history(call_id, {
                'decision_status': decision_status,
                'reference_price': entry_price,
                'price_usd': None,
                'liquidity_usd': None,
                'total_liquidity': None,
                'market_cap': None,
                'gain_loss_pct': None,
                'price_change_pct': None,
                'liquidity_change_pct': None,
                'market_cap_change_pct': None,
                'token_still_alive': 'no',
                'rug_pull_occurred': 'yes'
            })
            return
        if current_data['exists'] is None:
            print(f"  ⚠️  Market data unavailable, recording failure")
            tracker_logger.warning("Birdeye API failed for token",
                call_id=call_id, contract_address=contract_address[:16])
            # Record the failure in history so we know tracking was attempted
            self.db.insert_performance_history(call_id, {
                'decision_status': decision_status,
                'reference_price': entry_price,
                'price_usd': None,
                'liquidity_usd': None,
                'total_liquidity': None,
                'market_cap': None,
                'gain_loss_pct': None,
                'price_change_pct': None,
                'liquidity_change_pct': None,
                'market_cap_change_pct': None,
                'token_still_alive': 'unknown',
                'rug_pull_occurred': None
            })
            return

        current_price = current_data['price']
        current_liquidity = current_data['liquidity']
        total_liquidity = current_data.get('total_liquidity') or current_liquidity
        current_mcap = current_data['market_cap']

        if not current_price:
            print(f"  ⚠️  Could not get current price, recording failure")
            tracker_logger.warning("Birdeye missing price for token",
                call_id=call_id, contract_address=contract_address[:16])
            self.db.insert_or_update_performance(call_id, {
                'token_still_alive': 'unknown',
            })
            self.db.insert_performance_history(call_id, {
                'decision_status': decision_status,
                'reference_price': entry_price,
                'price_usd': None,
                'liquidity_usd': current_liquidity,
                'total_liquidity': total_liquidity,
                'market_cap': current_mcap,
                'gain_loss_pct': None,
                'price_change_pct': None,
                'liquidity_change_pct': None,
                'market_cap_change_pct': None,
                'token_still_alive': 'unknown',
                'rug_pull_occurred': None
            })
            return

        # Calculate gain/loss
        gain_loss = self.calculate_gain_loss(entry_price, current_price)

        if gain_loss is not None:
            print(f"  📊 Current: ${current_price:.10f} ({gain_loss:+.2f}%)")

        # Get existing performance data
        self.db.cursor.execute(
            'SELECT * FROM performance_tracking WHERE call_id = ?',
            (call_id,)
        )
        existing = self.db.cursor.fetchone()

        # Determine checkpoint type based on time elapsed
        checkpoint_type = None
        if minutes_since >= 1440:  # 24 hours
            checkpoint_type = '24h'
        elif minutes_since >= 240:  # 4 hours
            checkpoint_type = '4h'
        elif minutes_since >= 60:  # 1 hour
            checkpoint_type = '1h'
        elif minutes_since >= 15:  # 15 minutes
            checkpoint_type = '15m'

        # Prepare update data
        update_data = {
            'token_still_alive': 'yes',
            'current_mcap': current_mcap,
            'current_liquidity': current_liquidity,
            'checkpoint_type': checkpoint_type
        }

        # Track max and min prices since entry
        if not existing or not existing['max_price_since_entry'] or current_price > existing['max_price_since_entry']:
            update_data['max_price_since_entry'] = current_price

        if not existing or not existing['min_price_since_entry'] or current_price < existing['min_price_since_entry']:
            update_data['min_price_since_entry'] = current_price

        # Determine if this is a rug pull (liquidity dropped significantly or price near zero)
        if total_liquidity is not None and total_liquidity < 1000:
            update_data['rug_pull_occurred'] = 'yes'
            print(f"  🚨 RUG PULL DETECTED - Total Liquidity: ${total_liquidity:.2f}")
        elif current_price < (entry_price * 0.10):  # Price dropped 90%+
            update_data['rug_pull_occurred'] = 'yes'
            print(f"  🚨 RUG PULL SUSPECTED - Price crashed 90%+")

        # Update time-based price tracking
        if minutes_since >= 15 and (not existing or not existing.get('price_15m_later') is None):
            update_data['price_15m_later'] = current_price

        if minutes_since >= 30 and (not existing or not existing.get('price_30m_later') is None):
            update_data['price_30m_later'] = current_price

        if hours_since >= 1 and (not existing or not existing['price_1h_later']):
            update_data['price_1h_later'] = current_price

        if hours_since >= 24 and (not existing or not existing['price_24h_later']):
            update_data['price_24h_later'] = current_price

        if hours_since >= 168 and (not existing or not existing['price_7d_later']):  # 7 days
            update_data['price_7d_later'] = current_price

        if hours_since >= 720 and (not existing or not existing['price_30d_later']):  # 30 days
            update_data['price_30d_later'] = current_price

        # Update max gain/loss observed (cap at -100% minimum)
        if gain_loss is not None:
            # Cap gain_loss at -100% (can't lose more than 100%)
            capped_gain_loss = max(gain_loss, -100.0)

            if not existing or not existing['max_gain_observed'] or capped_gain_loss > existing['max_gain_observed']:
                update_data['max_gain_observed'] = capped_gain_loss
                # Record time to max gain and timestamp when a new max is hit
                update_data['time_to_max_gain_hours'] = hours_since
                update_data['max_gain_timestamp'] = datetime.now().isoformat()

            if not existing or not existing['max_loss_observed'] or capped_gain_loss < existing['max_loss_observed']:
                update_data['max_loss_observed'] = capped_gain_loss

        # Track time to rug — record hours since snapshot when rug is first detected
        if update_data.get('rug_pull_occurred') in ('yes', True):
            if not existing or not existing.get('time_to_rug_hours'):
                update_data['time_to_rug_hours'] = hours_since

        # Save to database
        self.db.insert_or_update_performance(call_id, update_data)

        # Insert time-series history snapshot
        last_history = self.db.get_latest_performance_history(call_id)
        price_change_pct = None
        liquidity_change_pct = None
        market_cap_change_pct = None
        if last_history:
            last_price = last_history.get('price_usd')
            last_liq = last_history.get('liquidity_usd')
            last_mcap = last_history.get('market_cap')
            if last_price:
                price_change_pct = ((current_price - last_price) / last_price) * 100
            if current_liquidity and last_liq:
                liquidity_change_pct = ((current_liquidity - last_liq) / last_liq) * 100
            if current_mcap and last_mcap:
                market_cap_change_pct = ((current_mcap - last_mcap) / last_mcap) * 100

        self.db.insert_performance_history(call_id, {
            'decision_status': decision_status,
            'reference_price': entry_price,
            'price_usd': current_price,
            'liquidity_usd': current_liquidity,
            'total_liquidity': total_liquidity,
            'market_cap': current_mcap,
            'gain_loss_pct': gain_loss,
            'price_change_pct': price_change_pct,
            'liquidity_change_pct': liquidity_change_pct,
            'market_cap_change_pct': market_cap_change_pct,
            'token_still_alive': update_data.get('token_still_alive'),
            'rug_pull_occurred': update_data.get('rug_pull_occurred'),
        })
        print(f"  ✅ Performance updated (checkpoint: {checkpoint_type})")

    def run_update(self, limit: int = None, min_age_hours: float = 0):
        """
        Run performance update for all tracked tokens.

        Args:
            limit: Maximum number of tokens to update (None = all)
            min_age_hours: Only update tokens older than this many hours
        """
        start_time = time.time()
        tracker_logger.info("Performance tracker started", limit=limit, min_age_hours=min_age_hours)

        print("="*60)
        print("📊 PERFORMANCE TRACKER")
        print("="*60)

        tokens = self.get_all_tracked_tokens()

        if not tokens:
            tracker_logger.warning("No active tokens to track")
            print("\n⚠️  No active tokens to track!")
            print("💡 Tokens are only tracked if they are WATCH or open TRADE positions.")
            print("💡 PASS decisions and closed trades (with exit recorded) are not tracked.")
            return

        # Filter by age if specified
        if min_age_hours > 0:
            tokens = [t for t in tokens
                     if self.calculate_time_since_snapshot(t['snapshot_timestamp']) >= min_age_hours]

        tracker_logger.info("Found tokens to update", token_count=len(tokens))
        print(f"\n📋 Found {len(tokens)} active token(s) to update (WATCH or open TRADE positions)")

        if limit:
            tokens = tokens[:limit]
            print(f"   Limiting to {limit} most recent")

        print()

        # Track all unique sources for updating stats later
        sources_to_update = set()
        updated_count = 0
        error_count = 0

        # Update each token
        for i, token in enumerate(tokens, 1):
            print(f"[{i}/{len(tokens)}] {token['token_symbol']} from {token['source']}")

            try:
                # Use actual trade entry price when available, otherwise fall back to call price
                entry_price = token.get('trade_entry_price') or token.get('call_price')
                self.update_token_performance(
                    call_id=token['call_id'],
                    contract_address=token['contract_address'],
                    entry_price=entry_price,
                    snapshot_timestamp=token['snapshot_timestamp'],
                    decision_status=token['my_decision'],
                    blockchain=token['blockchain']
                )
                updated_count += 1
            except Exception as e:
                error_count += 1
                tracker_logger.error("Failed to update token",
                    token=token['token_symbol'],
                    call_id=token['call_id'],
                    error=str(e)
                )

            # Split comma-separated sources and add each individually
            source_list = [s.strip() for s in token['source'].split(',') if s.strip()]
            for source in source_list:
                sources_to_update.add(source)

            # Rate limiting to avoid API throttling
            if i < len(tokens):
                time.sleep(1.0)  # Wait 1 second between requests

        # Update source performance stats for each individual source
        print(f"\n📈 Updating source statistics...")
        for source in sorted(sources_to_update):
            self.db.update_source_performance(source)
            print(f"  ✅ Updated {source}")

        duration_ms = round((time.time() - start_time) * 1000, 2)
        tracker_logger.info("Performance tracker completed",
            duration_ms=duration_ms,
            tokens_updated=updated_count,
            errors=error_count,
            sources_updated=len(sources_to_update)
        )

        print("\n" + "="*60)
        print("✅ Performance tracking complete!")
        print("="*60)

    def show_summary(self):
        """Show a summary of tracked tokens."""
        print("\n📊 TRACKING SUMMARY")
        print("─"*60)

        # Use comparison that works for both SQLite (text 'yes') and Postgres (boolean TRUE)
        self.db.cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN p.token_still_alive = 'yes' OR p.token_still_alive IS TRUE THEN 1 ELSE 0 END) as alive,
                SUM(CASE WHEN p.rug_pull_occurred = 'yes' OR p.rug_pull_occurred IS TRUE THEN 1 ELSE 0 END) as rugs,
                AVG(p.max_gain_observed) as avg_gain,
                MAX(p.max_gain_observed) as best_gain,
                MIN(p.max_loss_observed) as worst_loss
            FROM calls_received c
            LEFT JOIN performance_tracking p ON c.call_id = p.call_id
        ''')

        summary = dict(self.db.cursor.fetchone())

        print(f"Total Tracked: {summary['total']}")
        print(f"Still Alive: {summary['alive'] or 0}")
        print(f"Rug Pulls: {summary['rugs'] or 0}")

        if summary['avg_gain']:
            print(f"Avg Max Gain: {summary['avg_gain']:.2f}%")
        if summary['best_gain']:
            print(f"Best Gain: {summary['best_gain']:.2f}%")
        if summary['worst_loss']:
            print(f"Worst Loss: {summary['worst_loss']:.2f}%")

    def close(self):
        """Close database connection."""
        self.db.close()


def main():
    """Main entry point."""
    import argparse
    import os

    # Fail fast if BIRDEYE_API_KEY is missing
    if not os.environ.get('BIRDEYE_API_KEY'):
        print("❌ FATAL: BIRDEYE_API_KEY environment variable is not set!")
        print("💡 Set it in your environment or .env file")
        print("💡 For GitHub Actions, add it as a repository secret")
        raise SystemExit(1)

    parser = argparse.ArgumentParser(description='Track memecoin performance over time')
    parser.add_argument('-l', '--limit', type=int, help='Limit number of tokens to update')
    parser.add_argument('-a', '--min-age', type=float, default=0,
                       help='Only update tokens older than N hours')
    parser.add_argument('-s', '--summary', action='store_true',
                       help='Show summary only (no updates)')

    args = parser.parse_args()

    tracker = PerformanceTracker()

    try:
        if args.summary:
            tracker.show_summary()
        else:
            tracker.run_update(limit=args.limit, min_age_hours=args.min_age)
            tracker.show_summary()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Stopping...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tracker.close()


if __name__ == "__main__":
    main()
