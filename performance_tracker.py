#!/usr/bin/env python3
"""
Performance Tracker - Automatically updates token performance data

Run this script periodically (via cron or manually) to track token performance over time.
It will fetch current prices and update the performance_tracking table.
"""

import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher
from app_logger import tracker_logger, log_performance


class PerformanceTracker:
    """Tracks token performance over time."""

    # Dead letter queue file for failed requests
    DEAD_LETTER_FILE = "failed_requests.json"
    
    def __init__(self, max_workers: int = 3, use_parallel: bool = True):
        """Initialize tracker with database and fetcher.
        
        Args:
            max_workers: Maximum number of parallel threads for API calls
            use_parallel: Whether to use parallel processing for token updates
        """
        self.db = MemecoinDatabase()
        self.fetcher = MemecoinDataFetcher()
        self.max_workers = max_workers
        self.use_parallel = use_parallel

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
        query = self.db._placeholder()
        self.db.cursor.execute(
            f'SELECT * FROM performance_tracking WHERE call_id = {query}',
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

        # Track max and min prices since entry
        max_price = existing['max_price_since_entry'] if existing and existing['max_price_since_entry'] else entry_price
        min_price = existing['min_price_since_entry'] if existing and existing['min_price_since_entry'] else entry_price
        
        if current_price > max_price:
            update_data['max_price_since_entry'] = current_price
            max_price = current_price
        
        if current_price < min_price:
            update_data['min_price_since_entry'] = current_price
            min_price = current_price

        # Calculate max gain from max price reached (not current price)
        max_gain = ((max_price - entry_price) / entry_price) * 100 if entry_price else None
        min_gain = ((min_price - entry_price) / entry_price) * 100 if entry_price else None

        # Update max gain/loss observed (cap at -100% minimum)
        if max_gain is not None:
            # Cap at -100% (can't lose more than 100%)
            capped_max_gain = max(max_gain, -100.0)
            
            if not existing or not existing['max_gain_observed'] or capped_max_gain > existing['max_gain_observed']:
                update_data['max_gain_observed'] = capped_max_gain
                # Record time to max gain when a new max is hit
                update_data['time_to_max_gain_hours'] = hours_since
                update_data['max_gain_timestamp'] = datetime.now().isoformat()

        if min_gain is not None:
            # Cap at -100% (can't lose more than 100%)
            capped_min_gain = max(min_gain, -100.0)
            
            if not existing or not existing['max_loss_observed'] or capped_min_gain < existing['max_loss_observed']:
                update_data['max_loss_observed'] = capped_min_gain

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

        # Update each token (parallel or sequential)
        if self.use_parallel and len(tokens) > 1:
            updated_count, error_count = self._update_tokens_parallel(
                tokens, sources_to_update
            )
        else:
            updated_count, error_count = self._update_tokens_sequential(
                tokens, sources_to_update
            )

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

    def _update_single_token(self, token: Dict[str, Any]) -> Dict[str, Any]:
        """Update a single token's performance. Used for parallel processing.
        
        Returns:
            Dict with 'success', 'token', 'sources', and optional 'error' keys
        """
        result = {
            'success': False,
            'token': token,
            'sources': set(),
            'error': None
        }
        
        try:
            print(f"  Checking {token['token_symbol']} from {token['source']}...")
            
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
            result['success'] = True
            
            # Split comma-separated sources and add each individually
            source_list = [s.strip() for s in token['source'].split(',') if s.strip()]
            result['sources'] = set(source_list)
            
        except Exception as e:
            result['error'] = str(e)
            tracker_logger.error("Failed to update token",
                token=token['token_symbol'],
                call_id=token['call_id'],
                error=str(e)
            )
            # Add to dead letter queue
            self._add_to_dead_letter(token, str(e))
        
        return result
    
    def _update_tokens_parallel(self, tokens: List[Dict], sources_to_update: set) -> tuple:
        """Update tokens in parallel using ThreadPoolExecutor.
        
        Returns:
            Tuple of (updated_count, error_count)
        """
        updated_count = 0
        error_count = 0
        
        print(f"🚀 Using parallel processing with {self.max_workers} workers\n")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_token = {
                executor.submit(self._update_single_token, token): token 
                for token in tokens
            }
            
            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_token), 1):
                token = future_to_token[future]
                try:
                    result = future.result()
                    if result['success']:
                        updated_count += 1
                        sources_to_update.update(result['sources'])
                        print(f"  ✅ [{i}/{len(tokens)}] {token['token_symbol']} updated")
                    else:
                        error_count += 1
                        print(f"  ❌ [{i}/{len(tokens)}] {token['token_symbol']} failed: {result['error']}")
                except Exception as e:
                    error_count += 1
                    print(f"  ❌ [{i}/{len(tokens)}] {token['token_symbol']} exception: {e}")
        
        return updated_count, error_count
    
    def _update_tokens_sequential(self, tokens: List[Dict], sources_to_update: set) -> tuple:
        """Update tokens sequentially with rate limiting.
        
        Returns:
            Tuple of (updated_count, error_count)
        """
        updated_count = 0
        error_count = 0
        
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
                # Add to dead letter queue
                self._add_to_dead_letter(token, str(e))

            # Split comma-separated sources and add each individually
            source_list = [s.strip() for s in token['source'].split(',') if s.strip()]
            for source in source_list:
                sources_to_update.add(source)

            # Rate limiting to avoid API throttling
            if i < len(tokens):
                time.sleep(1.0)  # Wait 1 second between requests
        
        return updated_count, error_count
    
    def _add_to_dead_letter(self, token: Dict[str, Any], error: str) -> None:
        """Add a failed token update to the dead letter queue.
        
        Args:
            token: Token data that failed to update
            error: Error message
        """
        dead_letter_entry = {
            'timestamp': datetime.now().isoformat(),
            'call_id': token.get('call_id'),
            'token_symbol': token.get('token_symbol'),
            'contract_address': token.get('contract_address'),
            'blockchain': token.get('blockchain'),
            'source': token.get('source'),
            'error': error
        }
        
        try:
            # Load existing dead letter queue
            dead_letters = []
            if os.path.exists(self.DEAD_LETTER_FILE):
                with open(self.DEAD_LETTER_FILE, 'r') as f:
                    dead_letters = json.load(f)
            
            # Add new entry
            dead_letters.append(dead_letter_entry)
            
            # Keep only last 1000 entries to prevent file bloat
            dead_letters = dead_letters[-1000:]
            
            # Save back to file
            with open(self.DEAD_LETTER_FILE, 'w') as f:
                json.dump(dead_letters, f, indent=2)
                
            tracker_logger.warning("Added to dead letter queue",
                token=token.get('token_symbol'),
                call_id=token.get('call_id'))
        except Exception as e:
            tracker_logger.error("Failed to write to dead letter queue", error=str(e))
    
    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """Get all entries from the dead letter queue.
        
        Returns:
            List of dead letter entries
        """
        if not os.path.exists(self.DEAD_LETTER_FILE):
            return []
        
        try:
            with open(self.DEAD_LETTER_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            tracker_logger.error("Failed to read dead letter queue", error=str(e))
            return []
    
    def clear_dead_letter_queue(self) -> None:
        """Clear the dead letter queue."""
        if os.path.exists(self.DEAD_LETTER_FILE):
            try:
                os.remove(self.DEAD_LETTER_FILE)
                tracker_logger.info("Dead letter queue cleared")
            except Exception as e:
                tracker_logger.error("Failed to clear dead letter queue", error=str(e))
    
    def check_api_health(self) -> Dict[str, Any]:
        """Check health of all APIs before running updates.
        
        Returns:
            Dict with health status for each API
        """
        print("\n🔍 Checking API health...")
        health = self.fetcher.check_api_health()
        
        all_healthy = all(h['healthy'] for h in health.values())
        
        for api_name, status in health.items():
            if status['healthy']:
                print(f"  ✅ {api_name}: Healthy ({status['latency_ms']}ms)")
            else:
                error = status.get('error', 'Unknown error')
                print(f"  ❌ {api_name}: Unhealthy - {error}")
        
        if not all_healthy:
            print("\n⚠️  Some APIs are unhealthy. Updates may fail.")
        
        return health
    
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
    parser.add_argument('--sequential', action='store_true',
                       help='Use sequential processing instead of parallel')
    parser.add_argument('-w', '--workers', type=int, default=3,
                       help='Number of parallel workers (default: 3)')
    parser.add_argument('--health-check', action='store_true',
                       help='Check API health before running')
    parser.add_argument('--show-dead-letter', action='store_true',
                       help='Show dead letter queue and exit')
    parser.add_argument('--clear-dead-letter', action='store_true',
                       help='Clear dead letter queue and exit')

    args = parser.parse_args()

    tracker = PerformanceTracker(
        max_workers=args.workers,
        use_parallel=not args.sequential
    )
    
    # Handle dead letter queue commands
    if args.show_dead_letter:
        dead_letters = tracker.get_dead_letter_queue()
        print(f"\n📋 Dead Letter Queue ({len(dead_letters)} entries)")
        print("="*60)
        for entry in dead_letters[-20:]:  # Show last 20
            print(f"\n  {entry['timestamp']}")
            print(f"    Token: {entry['token_symbol']} ({entry['blockchain']})")
            print(f"    Error: {entry['error'][:100]}...")
        return
    
    if args.clear_dead_letter:
        tracker.clear_dead_letter_queue()
        print("✅ Dead letter queue cleared")
        return
    
    # Check API health if requested
    if args.health_check:
        health = tracker.check_api_health()
        if not all(h['healthy'] for h in health.values()):
            print("\n❌ Some APIs are unhealthy. Exiting.")
            return

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
