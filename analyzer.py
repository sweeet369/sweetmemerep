#!/usr/bin/env python3
"""
Memecoin Trading Analyzer - Main CLI Interface
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from app_logger import analyzer_logger as logger
from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher
from display import (
    display_analysis, format_currency, get_safety_rating, get_tier_emoji,
    print_header, print_menu,
    TIER_EMOJI, DEFAULT_TIER_EMOJI, SAFETY_THRESHOLDS,
    HONEYPOT_EMOJI, PRESSURE_EMOJI, MOMENTUM_EMOJI, VOLUME_EMOJI, CONCENTRATION_EMOJI,
)

# =============================================================================
# LOGGING SETUP
# =============================================================================

# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

T = TypeVar('T')
TokenData = dict[str, Any]
WalletInfo = dict[str, Any]


@dataclass(frozen=True)
class Result(Generic[T]):
    """Result type for explicit error handling."""
    success: bool
    data: T | None = None
    error: str | None = None

    @classmethod
    def ok(cls, data: T) -> Result[T]:
        return cls(success=True, data=data)

    @classmethod
    def err(cls, error: str) -> Result[T]:
        return cls(success=False, error=error)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class AnalyzerError(Exception):
    """Base exception for analyzer errors."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message
        logger.error(f"{self.__class__.__name__}: {message}")


class TokenNotFoundError(AnalyzerError):
    """Token doesn't exist or couldn't be fetched."""
    pass


class DatabaseError(AnalyzerError):
    """Database operation failed."""
    pass


class APIError(AnalyzerError):
    """External API call failed."""
    pass


class ValidationError(AnalyzerError):
    """Input validation failed."""
    pass


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_contract_address(address: str) -> Result[str]:
    """Validate contract address format."""
    address = address.strip()
    if not address:
        return Result.err("Contract address is required")
    if len(address) < 32:
        return Result.err("Contract address too short (minimum 32 characters)")
    if len(address) > 50:
        return Result.err("Contract address too long (maximum 50 characters)")
    return Result.ok(address)


def validate_positive_number(value: str, field_name: str) -> Result[float]:
    """Validate that input is a positive number."""
    value = value.strip()
    if not value:
        return Result.err(f"{field_name} is required")
    try:
        num = float(value)
        if num <= 0:
            return Result.err(f"{field_name} must be positive")
        return Result.ok(num)
    except ValueError:
        return Result.err(f"{field_name} must be a valid number")


def validate_confidence_level(value: str) -> Result[int]:
    """Validate confidence level (1-10)."""
    value = value.strip()
    if not value:
        return Result.ok(5)  # Default
    try:
        level = int(value)
        if level < 1 or level > 10:
            return Result.err("Confidence must be between 1 and 10")
        return Result.ok(level)
    except ValueError:
        return Result.err("Confidence must be a number")


class MemecoinAnalyzer:
    """Main CLI interface for memecoin analysis."""

    def __init__(self) -> None:
        """Initialize analyzer with database and data fetcher."""
        self.db: MemecoinDatabase = MemecoinDatabase()
        self.fetcher: MemecoinDataFetcher = MemecoinDataFetcher()
        logger.info("MemecoinAnalyzer initialized")

    def analyze_new_call(self) -> None:
        """Analyze a new memecoin call."""
        print("\n" + "━"*60)
        print("📞 NEW CALL ANALYSIS")
        print("━"*60)

        # Get and validate contract address
        address_input = input("\nContract address: ")
        address_result = validate_contract_address(address_input)
        if not address_result.success:
            print(f"❌ {address_result.error}")
            return
        contract_address = address_result.data

        # Get source(s) - allow comma-separated
        source_input = input("Source name(s) - comma-separated for multiple (e.g., 'Alpha Group #3, Twitter Call'): ").strip()
        if not source_input:
            source = "unknown"
        else:
            source = self.db.normalize_sources(source_input)

        # Get blockchain
        blockchain = input("Blockchain [Solana/Base/Ethereum/BSC/Polygon/Arbitrum] (default Solana): ").strip()
        if not blockchain:
            blockchain = "Solana"

        print(f"\n⏳ Fetching data for {contract_address}...")
        print("━"*60)
        logger.info(f"Analyzing token: {contract_address} from source: {source}")

        # Get tracked wallets for smart money detection
        tracked_wallets = self.db.get_all_wallets()

        # Fetch data (with smart money detection)
        try:
            data = self.fetcher.fetch_all_data(contract_address, tracked_wallets=tracked_wallets, blockchain=blockchain)
        except Exception as e:
            logger.error(f"Failed to fetch data for {contract_address}: {e}", exc_info=True)
            print(f"\n❌ API error: {e}")
            return

        if not data:
            logger.warning(f"No data returned for token: {contract_address}")
            print("\n❌ Failed to fetch token data. Token may not exist or APIs are unavailable.")
            return

        # Get token info from unified data (Birdeye)
        token_name = data.get('token_name') or "Unknown"
        token_symbol = data.get('token_symbol') or "Unknown"

        # Insert call to database
        call_id = self.db.insert_call(
            contract_address=contract_address,
            token_symbol=token_symbol,
            token_name=token_name,
            source=source,
            blockchain=blockchain
        )

        # Insert snapshot
        self.db.insert_snapshot(call_id, data)

        # Display analysis
        display_analysis(token_symbol, token_name, source, data)

        # Get user decision
        self.get_user_decision(call_id, contract_address, data)

        # Update source performance for all sources
        sources = [self.db.normalize_source_name(s) for s in source.split(',')]
        for src in sources:
            self.db.update_source_performance(src)

        print(f"\n✅ Saved to database (Call ID: {call_id})")

    def get_user_decision(self, call_id: int, contract_address: str, data: TokenData) -> None:
        """Get and record user's trading decision.

        Args:
            call_id: Database ID of the call
            contract_address: Token contract address
            data: Token data dictionary
        """
        print(f"\n🤔 YOUR DECISION:")

        # Get decision
        decision_input = input("[T]RADE / [P]ASS / [W]ATCH? ").strip().upper()

        if decision_input in ['T', 'TRADE']:
            decision = 'TRADE'
        elif decision_input in ['P', 'PASS']:
            decision = 'PASS'
        elif decision_input in ['W', 'WATCH']:
            decision = 'WATCH'
        else:
            print("Invalid choice, recording as PASS")
            decision = 'PASS'

        # Get additional details
        trade_size_usd = None
        entry_price = data.get('price_usd')  # Default to call price
        entry_timestamp = None
        chart_assessment = None

        if decision == 'TRADE':
            # Fetch CURRENT price for entry (not snapshot price which is the call price)
            print("\n⏳ Fetching current price for entry...")
            current_data = self.fetcher.fetch_birdeye_data(contract_address, blockchain=blockchain)
            if current_data:
                entry_price = current_data.get('price_usd')
                print(f"💰 Current Entry Price: ${entry_price:.10f}")
            else:
                print(f"⚠️  Could not fetch current price, using call price: ${entry_price:.10f}")

            entry_timestamp = datetime.now().isoformat()
            try:
                trade_size_input = input("💵 Position size (USD): ").strip()
                if trade_size_input:
                    trade_size_usd = float(trade_size_input)
            except ValueError:
                print("⚠️  Invalid amount, recording without position size")

            # Chart assessment
            chart_input = input("📊 Chart assessment? [S]trong / [N]eutral / [W]eak: ").strip().upper()
            if chart_input in ['S', 'STRONG']:
                chart_assessment = 'STRONG'
            elif chart_input in ['N', 'NEUTRAL']:
                chart_assessment = 'NEUTRAL'
            elif chart_input in ['W', 'WEAK']:
                chart_assessment = 'WEAK'
            else:
                chart_assessment = 'NEUTRAL'

        # Get notes
        reasoning_notes = input("📝 Notes: ").strip()
        if not reasoning_notes:
            reasoning_notes = "No notes"

        # Get emotional state
        emotional_state = input("😊 Emotional state [calm/fomo/uncertain]: ").strip().lower()
        if not emotional_state:
            emotional_state = "calm"

        # Get confidence level
        try:
            confidence_input = input("🎯 Confidence (1-10): ").strip()
            confidence_level = int(confidence_input) if confidence_input else 5
            confidence_level = max(1, min(10, confidence_level))
        except ValueError:
            confidence_level = 5

        # Save decision to database
        self.db.insert_decision(
            call_id=call_id,
            decision=decision,
            trade_size_usd=trade_size_usd,
            entry_price=entry_price,
            reasoning_notes=reasoning_notes,
            emotional_state=emotional_state,
            confidence_level=confidence_level,
            chart_assessment=chart_assessment,
            entry_timestamp=entry_timestamp
        )

    def view_source_stats(self) -> None:
        """Display statistics for all tracked sources."""
        print("\n" + "━"*60)
        print("📊 SOURCE PERFORMANCE STATISTICS")
        print("━"*60)

        sources = self.db.get_all_sources()

        if not sources:
            print("\n⚠️  No source data available yet. Analyze some calls first!")
            return

        print(f"\n{'Tier':<6} {'Source':<20} {'n=':<5} {'Hit%':<7} {'Recent':<7} {'Avg Gain':<10} {'Alpha':<8} {'Conf':<6} {'Peak Time':<10} {'Rug%':<6}")
        print("─"*105)

        for source in sources:
            tier = source['tier']
            name = source['source_name'][:19]
            total = source['total_calls']
            hit_rate = source.get('hit_rate', 0.0) * 100
            avg_gain = source['avg_max_gain']
            rug_rate = source['rug_rate'] * 100

            # Add tier emoji
            tier_emoji = get_tier_emoji(tier)

            # New metrics
            sample_size = source.get('sample_size') or total
            alpha = source.get('baseline_alpha')
            confidence = source.get('confidence_score')
            recent_hr = source.get('recent_hit_rate')
            avg_peak_time = source.get('avg_time_to_max_gain_hours')

            # Format alpha with +/- prefix
            if alpha is not None:
                alpha_str = f"{alpha:+.1f}%"
            else:
                alpha_str = "  N/A"

            # Format confidence as percentage
            if confidence is not None:
                conf_str = f"{confidence * 100:.0f}%"
            else:
                conf_str = " N/A"

            # Format recent hit rate
            if recent_hr is not None:
                recent_str = f"{recent_hr * 100:.0f}%"
            else:
                recent_str = "  N/A"

            # Format avg peak time in hours or days
            if avg_peak_time is not None:
                if avg_peak_time >= 24:
                    peak_str = f"{avg_peak_time / 24:.1f}d"
                else:
                    peak_str = f"{avg_peak_time:.1f}h"
            else:
                peak_str = "N/A"

            print(f"{tier_emoji} {tier:<4} {name:<20} {sample_size:<5} {hit_rate:>5.1f}% {recent_str:>6} {avg_gain:>8.1f}% {alpha_str:>7} {conf_str:>5} {peak_str:>9} {rug_rate:>5.1f}%")

    def view_watchlist(self) -> None:
        """Display performance of all tokens in watchlist."""
        print("\n" + "━"*60)
        print("👀 WATCHLIST PERFORMANCE")
        print("━"*60)

        # Query all WATCH decisions with token data
        try:
            self.db.cursor.execute('''
                SELECT
                    c.call_id,
                    c.token_symbol,
                    c.token_name,
                    c.contract_address,
                    c.source,
                    s.price_usd as entry_price,
                    s.snapshot_timestamp,
                    s.safety_score,
                    s.liquidity_usd as entry_liquidity,
                    s.market_cap as initial_mcap,
                    s.raw_data as raw_data,
                    d.timestamp_decision,
                    d.reasoning_notes,
                    d.confidence_level,
                    p.current_mcap as tracked_mcap,
                    p.current_liquidity as tracked_liquidity,
                    p.max_gain_observed,
                    p.max_loss_observed,
                    p.token_still_alive,
                    p.rug_pull_occurred,
                    p.last_updated,
                    ph.price_usd as current_price,
                    ph.liquidity_usd as current_liquidity,
                    ph.market_cap as current_mcap,
                    ph.timestamp as current_timestamp
                FROM calls_received c
                JOIN my_decisions d ON c.call_id = d.call_id
                JOIN initial_snapshot s ON c.call_id = s.call_id
                LEFT JOIN performance_tracking p ON c.call_id = p.call_id
                LEFT JOIN (
                    SELECT ph1.*
                    FROM performance_history ph1
                    JOIN (
                        SELECT call_id, MAX(timestamp) as max_ts
                        FROM performance_history
                        GROUP BY call_id
                    ) ph2
                    ON ph1.call_id = ph2.call_id AND ph1.timestamp = ph2.max_ts
                ) ph ON ph.call_id = c.call_id
                WHERE d.my_decision = 'WATCH'
                ORDER BY d.timestamp_decision DESC
            ''')
        except Exception as e:
            logger.warning("performance_history unavailable, using tracked snapshot only", error=str(e))
            self.db.cursor.execute('''
                SELECT
                    c.call_id,
                    c.token_symbol,
                    c.token_name,
                    c.contract_address,
                    c.source,
                    s.price_usd as entry_price,
                    s.snapshot_timestamp,
                    s.safety_score,
                    s.liquidity_usd as entry_liquidity,
                    s.market_cap as initial_mcap,
                    s.raw_data as raw_data,
                    d.timestamp_decision,
                    d.reasoning_notes,
                    d.confidence_level,
                    p.current_mcap as tracked_mcap,
                    p.current_liquidity as tracked_liquidity,
                    p.max_gain_observed,
                    p.max_loss_observed,
                    p.token_still_alive,
                    p.rug_pull_occurred,
                    p.last_updated
                FROM calls_received c
                JOIN my_decisions d ON c.call_id = d.call_id
                JOIN initial_snapshot s ON c.call_id = s.call_id
                LEFT JOIN performance_tracking p ON c.call_id = p.call_id
                WHERE d.my_decision = 'WATCH'
                ORDER BY d.timestamp_decision DESC
            ''')

        watchlist = [dict(row) for row in self.db.cursor.fetchall()]

        if not watchlist:
            print("\n⚠️  Your watchlist is empty. Mark tokens as WATCH to track them!")
            return

        print(f"\n📋 Watching {len(watchlist)} token(s)\n")

        for i, token in enumerate(watchlist, 1):
            # Backfill token symbol/name from snapshot raw_data if missing
            if (not token.get('token_symbol') or token.get('token_symbol') == 'Unknown' or
                not token.get('token_name') or token.get('token_name') == 'Unknown'):
                raw = token.get('raw_data')
                if raw:
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except json.JSONDecodeError:
                            raw = None
                    if isinstance(raw, dict):
                        name = None
                        symbol = None
                        birdeye_raw = raw.get('birdeye', {}) if raw else {}
                        if birdeye_raw:
                            name = birdeye_raw.get('name')
                            symbol = birdeye_raw.get('symbol')
                        if name or symbol:
                            self.db._execute('''
                                UPDATE calls_received
                                SET token_symbol = ?, token_name = ?
                                WHERE call_id = ?
                            ''', (symbol or token.get('token_symbol'), name or token.get('token_name'), token['call_id']))
                            self.db.conn.commit()
                            token['token_symbol'] = symbol or token.get('token_symbol')
                            token['token_name'] = name or token.get('token_name')
            # Header for each token
            print("─"*60)
            print(f"[{i}] ${token['token_symbol']} - {token['token_name']}")
            print(f"    📍 Source: {token['source']}")
            print(f"    🔗 {token['contract_address'][:20]}...")

            # Safety and entry info
            safety_score = token['safety_score'] or 0
            rating, emoji = get_safety_rating(safety_score)
            print(f"    {emoji} Safety Score: {safety_score:.1f}/10 ({rating})")
            print(f"    💧 Entry Liquidity: {format_currency(token['entry_liquidity'])}")

            # Market cap info
            initial_mcap = token.get('initial_mcap')
            current_mcap = token.get('current_mcap') or token.get('tracked_mcap')
            if initial_mcap:
                print(f"    💰 Initial MCap: {format_currency(initial_mcap)}")
            if current_mcap:
                mcap_change = ((current_mcap - initial_mcap) / initial_mcap * 100) if initial_mcap else 0
                mcap_indicator = "📈" if mcap_change > 0 else "📉" if mcap_change < 0 else "➡️"
                print(f"    {mcap_indicator} Current MCap: {format_currency(current_mcap)} ({mcap_change:+.1f}%)")

            # Liquidity tracking
            entry_liquidity = token.get('entry_liquidity')
            current_liquidity = token.get('current_liquidity') or token.get('tracked_liquidity')
            if current_liquidity and entry_liquidity:
                liq_change = ((current_liquidity - entry_liquidity) / entry_liquidity * 100) if entry_liquidity else 0
                liq_indicator = "📈" if liq_change > 0 else "📉" if liq_change < 0 else "➡️"
                print(f"    {liq_indicator} Current Liquidity: {format_currency(current_liquidity)} ({liq_change:+.1f}%)")

            # Current price
            current_price = token.get('current_price')
            if current_price:
                entry_price = token.get('entry_price') or 0
                price_change = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
                price_indicator = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
                print(f"    {price_indicator} Current Price: ${current_price:.10f} ({price_change:+.1f}%)")

            # Decision info
            if token['timestamp_decision']:
                ts = token['timestamp_decision']
                decision_time = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
                # Strip timezone info for comparison with datetime.now()
                if decision_time.tzinfo is not None:
                    decision_time = decision_time.replace(tzinfo=None)
                days_ago = (datetime.now() - decision_time).days
                hours_ago = (datetime.now() - decision_time).seconds // 3600

                if days_ago > 0:
                    print(f"    ⏱️  Added: {days_ago}d ago")
                else:
                    print(f"    ⏱️  Added: {hours_ago}h ago")

            if token['reasoning_notes']:
                print(f"    📝 Notes: {token['reasoning_notes'][:50]}")

            # Performance tracking
            if token['rug_pull_occurred'] == 'yes':
                print(f"    🚨 RUG PULL DETECTED - Token rugged!")
            elif token['token_still_alive'] == 'no':
                print(f"    ❌ Token no longer exists")
            elif token['max_gain_observed'] is not None:
                gain = token['max_gain_observed']
                loss = token['max_loss_observed'] or 0

                if gain > 0:
                    print(f"    📈 Best Performance: +{gain:.2f}%")
                if loss < 0:
                    print(f"    📉 Worst Drop: {loss:.2f}%")

                # Status indicator
                if gain > 100:
                    print(f"    🚀 MAJOR PUMP - Consider entry!")
                elif gain > 50:
                    print(f"    ⬆️  Strong pump - Good opportunity")
                elif gain > 0:
                    print(f"    ✅ Positive movement")
                elif loss < -50:
                    print(f"    ⚠️  Major dump - May be dead")
                else:
                    print(f"    ➡️  Stable/Minor movement")

                last_ts = token.get('current_timestamp') or token.get('last_updated')
                if last_ts:
                    lu = last_ts
                    update_time = lu if isinstance(lu, datetime) else datetime.fromisoformat(str(lu))
                    if update_time.tzinfo is not None:
                        update_time = update_time.replace(tzinfo=None)
                    update_mins_ago = (datetime.now() - update_time).seconds // 60
                    print(f"    🔄 Last updated: {update_mins_ago}m ago")
            else:
                if not (current_price or current_liquidity or current_mcap):
                    print(f"    ⏳ Waiting for performance data...")
                    print(f"    💡 Run: python3 performance_tracker.py")
                last_ts = token.get('current_timestamp') or token.get('last_updated')
                if last_ts:
                    lu = last_ts
                    update_time = lu if isinstance(lu, datetime) else datetime.fromisoformat(str(lu))
                    if update_time.tzinfo is not None:
                        update_time = update_time.replace(tzinfo=None)
                    update_mins_ago = (datetime.now() - update_time).seconds // 60
                    print(f"    🔄 Last updated: {update_mins_ago}m ago")

        print("─"*60)
        print(f"\n💡 Tip: Tokens showing strong gains may be good entry opportunities!")
        print(f"💡 To remove from watchlist, use option [9] Remove from watchlist")

    def view_open_positions(self) -> None:
        """Display all open trading positions with current performance."""
        print("\n" + "="*70)
        print("📈 OPEN POSITIONS")
        print("="*70)

        # Get all TRADE decisions without exit
        self.db.cursor.execute('''
            SELECT
                c.call_id, c.contract_address, c.token_symbol, c.token_name, c.source, c.blockchain,
                s.price_usd as call_price,
                s.liquidity_usd as entry_liquidity,
                s.market_cap as entry_mcap,
                d.entry_price,
                d.entry_timestamp,
                d.trade_size_usd,
                d.chart_assessment,
                d.confidence_level,
                d.reasoning_notes,
                d.timestamp_decision,
                p.max_gain_observed,
                p.max_loss_observed,
                p.rug_pull_occurred
            FROM calls_received c
            JOIN my_decisions d ON c.call_id = d.call_id
            JOIN initial_snapshot s ON c.call_id = s.call_id
            LEFT JOIN performance_tracking p ON c.call_id = p.call_id
            WHERE d.my_decision = 'TRADE'
            AND (d.actual_exit_price IS NULL OR d.actual_exit_price = 0)
            ORDER BY d.entry_timestamp DESC
        ''')

        positions = [dict(row) for row in self.db.cursor.fetchall()]

        if not positions:
            print("\n📭 No open positions. You're all cash!")
            print("💡 Use [1] Analyze new call or [7] Convert WATCH to TRADE to open positions.")
            return

        # Calculate totals
        total_invested = 0
        total_current_value = 0
        total_pnl_usd = 0

        print(f"\n📊 You have {len(positions)} open position(s)\n")
        print("─"*70)

        for i, pos in enumerate(positions, 1):
            symbol = pos['token_symbol'] or 'Unknown'
            name = pos['token_name'] or 'Unknown'
            source = pos['source'] or 'Unknown'

            # Fetch current price
            current_data = self.fetcher.fetch_birdeye_data(pos['contract_address'], blockchain=pos.get('blockchain', 'solana'))
            current_price = current_data.get('price_usd') if current_data else None
            current_liquidity = current_data.get('liquidity_usd') if current_data else None
            current_mcap = current_data.get('market_cap') if current_data else None

            # Calculate P&L
            entry_price = pos['entry_price'] or pos['call_price']
            call_price = pos['call_price']
            trade_size = pos['trade_size_usd'] or 0

            if current_price and entry_price:
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
                pnl_from_call = ((current_price - call_price) / call_price) * 100 if call_price else 0

                if trade_size > 0:
                    current_value = trade_size * (1 + pnl_percent/100)
                    pnl_usd = current_value - trade_size
                    total_invested += trade_size
                    total_current_value += current_value
                    total_pnl_usd += pnl_usd
            else:
                pnl_percent = 0
                pnl_from_call = 0
                current_value = trade_size
                pnl_usd = 0

            # Display position
            pnl_emoji = "🟢" if pnl_percent > 0 else "🔴" if pnl_percent < 0 else "⚪"

            print(f"\n[{i}] {pnl_emoji} ${symbol} - {name}")
            print(f"    📍 Source: {source}")
            print(f"    🔗 {pos['contract_address'][:30]}...")

            # Price info
            print(f"\n    💵 PRICES:")
            print(f"       📞 Call Price:    ${call_price:.10f}" if call_price else "       📞 Call Price:    N/A")
            print(f"       💰 Entry Price:   ${entry_price:.10f}" if entry_price else "       💰 Entry Price:   N/A")
            print(f"       📊 Current Price: ${current_price:.10f}" if current_price else "       📊 Current Price: N/A")

            # P&L
            print(f"\n    📈 PERFORMANCE:")
            if pnl_percent != 0:
                pnl_indicator = "📈" if pnl_percent > 0 else "📉"
                print(f"       {pnl_indicator} P&L from Entry: {pnl_percent:+.2f}%")
                print(f"       {pnl_indicator} P&L from Call:  {pnl_from_call:+.2f}%")

            # Position size
            if trade_size > 0:
                print(f"\n    💼 POSITION:")
                print(f"       Invested:  ${trade_size:,.2f}")
                print(f"       Current:   ${current_value:,.2f}")
                print(f"       P&L (USD): ${pnl_usd:+,.2f}")

            # Max gain/loss observed
            if pos['max_gain_observed'] is not None:
                print(f"\n    📊 RANGE:")
                print(f"       Best:  {pos['max_gain_observed']:+.2f}%")
                print(f"       Worst: {pos['max_loss_observed']:.2f}%")

            # Liquidity check
            if current_liquidity:
                liq_change = ((current_liquidity - pos['entry_liquidity']) / pos['entry_liquidity'] * 100) if pos['entry_liquidity'] else 0
                liq_emoji = "🟢" if liq_change > 0 else "🔴" if liq_change < -30 else "🟡"
                print(f"\n    💧 LIQUIDITY:")
                print(f"       {liq_emoji} Current: {format_currency(current_liquidity)} ({liq_change:+.1f}%)")

            # Trade details
            print(f"\n    📝 DETAILS:")
            if pos['chart_assessment']:
                print(f"       Chart: {pos['chart_assessment']}")
            if pos['confidence_level']:
                print(f"       Confidence: {pos['confidence_level']}/10")
            if pos['reasoning_notes']:
                print(f"       Notes: {pos['reasoning_notes'][:40]}...")

            # Entry time
            if pos['entry_timestamp']:
                et = pos['entry_timestamp']
                entry_time = et if isinstance(et, datetime) else datetime.fromisoformat(str(et))
                if entry_time.tzinfo is not None:
                    entry_time = entry_time.replace(tzinfo=None)
                days_held = (datetime.now() - entry_time).days
                hours_held = (datetime.now() - entry_time).seconds // 3600
                if days_held > 0:
                    print(f"       Held: {days_held}d {hours_held}h")
                else:
                    print(f"       Held: {hours_held}h")

            # Rug warning
            if pos['rug_pull_occurred'] == 'yes':
                print(f"\n    🚨 WARNING: RUG PULL DETECTED!")

            print("─"*70)

        # Portfolio summary
        if total_invested > 0:
            total_pnl_percent = ((total_current_value - total_invested) / total_invested) * 100
            summary_emoji = "🟢" if total_pnl_percent > 0 else "🔴" if total_pnl_percent < 0 else "⚪"

            print(f"\n{'='*70}")
            print(f"📊 PORTFOLIO SUMMARY")
            print(f"{'='*70}")
            print(f"   Total Invested:     ${total_invested:,.2f}")
            print(f"   Current Value:      ${total_current_value:,.2f}")
            print(f"   {summary_emoji} Total P&L:          ${total_pnl_usd:+,.2f} ({total_pnl_percent:+.2f}%)")
            print(f"{'='*70}")

        print(f"\n💡 Tips:")
        print(f"   • Use [8] Record exit to close a position")
        print(f"   • Run 'python3 performance_tracker.py' to update max gain/loss")

    def convert_watch_to_trade(self) -> None:
        """Convert a WATCH decision to TRADE and record entry."""
        print("\n" + "━"*60)
        print("📈 CONVERT WATCH TO TRADE")
        print("━"*60)

        # Get watchlist tokens with performance data
        self.db.cursor.execute('''
            SELECT
                c.call_id,
                c.token_symbol,
                c.token_name,
                c.contract_address,
                c.blockchain,
                d.timestamp_decision,
                p.current_price,
                p.max_gain_observed,
                s.price_usd as call_price
            FROM calls_received c
            JOIN my_decisions d ON c.call_id = d.call_id
            LEFT JOIN performance_tracking p ON c.call_id = p.call_id
            LEFT JOIN initial_snapshot s ON c.call_id = s.call_id
            WHERE d.my_decision = 'WATCH'
            ORDER BY d.timestamp_decision DESC
        ''')

        watchlist = [dict(row) for row in self.db.cursor.fetchall()]

        if not watchlist:
            print("\n⚠️  Your watchlist is empty!")
            return

        # Display watchlist with performance
        print(f"\n📋 Watchlist ({len(watchlist)} tokens):\n")
        for i, token in enumerate(watchlist, 1):
            print(f"[{i}] ${token['token_symbol']} - {token['token_name']}")
            print(f"    🔗 {token['contract_address'][:40]}...")

            call_price = token.get('call_price')
            current_price = token.get('current_price')
            max_gain = token.get('max_gain_observed')

            if call_price:
                print(f"    💰 Call Price: ${call_price:.10f}")
            if current_price:
                print(f"    📊 Current Price: ${current_price:.10f}")
            if max_gain:
                print(f"    🚀 Max Gain: {max_gain:.2f}%")
            print()

        # Get user selection
        try:
            selection = int(input("Select token number to convert to TRADE (or 0 to cancel): ").strip())
            if selection == 0:
                return
            if selection < 1 or selection > len(watchlist):
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Invalid input")
            return

        selected_token = watchlist[selection - 1]
        call_id = selected_token['call_id']
        contract_address = selected_token['contract_address']

        print(f"\n🔄 Converting ${selected_token['token_symbol']} to TRADE...")

        # Fetch CURRENT price for entry
        print("\n⏳ Fetching current price for entry...")
        current_data = self.fetcher.fetch_birdeye_data(contract_address, blockchain=selected_token.get('blockchain', 'solana'))

        if current_data:
            entry_price = current_data.get('price_usd')
            print(f"💰 Current Entry Price: ${entry_price:.10f}")
        else:
            print(f"⚠️  Could not fetch current price, using last tracked price")
            entry_price = selected_token.get('current_price') or selected_token.get('call_price')
            if entry_price:
                print(f"💰 Entry Price: ${entry_price:.10f}")
            else:
                print("❌ Could not determine entry price")
                return

        entry_timestamp = datetime.now().isoformat()

        # Get TRADE details
        print(f"\n📝 Enter trade details:")

        # Trade size
        try:
            trade_size_input = input("💵 Trade size (USD, e.g., 100): ").strip()
            if trade_size_input:
                trade_size_usd = float(trade_size_input)
            else:
                print("❌ Trade size is required")
                return
        except ValueError:
            print("❌ Invalid trade size")
            return

        # Chart assessment
        chart_assessment = input("📊 Chart assessment (optional): ").strip()
        if not chart_assessment:
            chart_assessment = None

        # Reasoning
        reasoning_notes = input("💭 Reasoning (why converting to TRADE?): ").strip()
        if not reasoning_notes:
            reasoning_notes = "Converting from watchlist"

        # Emotional state
        emotional_state = input("😊 Emotional state [calm/fomo/uncertain]: ").strip().lower()
        if not emotional_state:
            emotional_state = "calm"

        # Confidence level
        try:
            confidence_input = input("🎯 Confidence (1-10): ").strip()
            confidence_level = int(confidence_input) if confidence_input else 5
            confidence_level = max(1, min(10, confidence_level))
        except ValueError:
            confidence_level = 5

        # Update the decision from WATCH to TRADE with new entry price
        self.db.cursor.execute('''
            UPDATE my_decisions
            SET my_decision = 'TRADE',
                trade_size_usd = ?,
                entry_price = ?,
                entry_timestamp = ?,
                reasoning_notes = ?,
                emotional_state = ?,
                confidence_level = ?,
                chart_assessment = ?
            WHERE call_id = ? AND my_decision = 'WATCH'
        ''', (trade_size_usd, entry_price, entry_timestamp, reasoning_notes,
              emotional_state, confidence_level, chart_assessment, call_id))

        self.db.conn.commit()

        print(f"\n✅ ${selected_token['token_symbol']} converted to TRADE!")
        print(f"💰 Entry Price: ${entry_price:.10f}")
        print(f"💵 Trade Size: ${trade_size_usd:.2f}")
        print(f"\n💡 Original call price preserved in initial_snapshot")
        print(f"💡 Track exit using option [6] Record exit")

    def remove_from_watchlist(self) -> None:
        """Remove a token from the watchlist."""
        print("\n" + "━"*60)
        print("🗑️  REMOVE FROM WATCHLIST")
        print("━"*60)

        # Get watchlist tokens
        self.db.cursor.execute('''
            SELECT
                c.call_id,
                c.token_symbol,
                c.token_name,
                c.contract_address,
                d.timestamp_decision
            FROM calls_received c
            JOIN my_decisions d ON c.call_id = d.call_id
            WHERE d.my_decision = 'WATCH'
            ORDER BY d.timestamp_decision DESC
        ''')

        watchlist = [dict(row) for row in self.db.cursor.fetchall()]

        if not watchlist:
            print("\n⚠️  Your watchlist is empty!")
            return

        # Display watchlist
        print(f"\n📋 Watchlist ({len(watchlist)} tokens):\n")
        for i, token in enumerate(watchlist, 1):
            print(f"[{i}] ${token['token_symbol']} - {token['token_name']}")
            print(f"    🔗 {token['contract_address'][:30]}...")

        # Get user selection
        try:
            selection = int(input("\nSelect token number to remove (or 0 to cancel): ").strip())
            if selection == 0:
                return
            if selection < 1 or selection > len(watchlist):
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Invalid input")
            return

        selected_token = watchlist[selection - 1]

        # Confirm removal
        confirm = input(f"\n⚠️  Remove ${selected_token['token_symbol']} from watchlist? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

        # Change decision from WATCH to PASS
        self.db.cursor.execute('''
            UPDATE my_decisions
            SET my_decision = 'PASS'
            WHERE call_id = ? AND my_decision = 'WATCH'
        ''', (selected_token['call_id'],))
        self.db.conn.commit()

        print(f"\n✅ ${selected_token['token_symbol']} removed from watchlist")

    def manage_tracked_wallets(self) -> None:
        """Manage smart money tracked wallets."""
        while True:
            print("\n" + "━"*60)
            print("💰 TRACKED WALLETS MANAGEMENT")
            print("━"*60)
            print("\nOptions:")
            print("  [1] Add wallet")
            print("  [2] Remove wallet")
            print("  [3] View all wallets")
            print("  [4] Import from file")
            print("  [5] Back to main menu")
            print()

            choice = input("Your choice: ").strip()

            if choice == '1':
                self.add_wallet()
            elif choice == '2':
                self.remove_wallet()
            elif choice == '3':
                self.view_all_wallets()
            elif choice == '4':
                self.import_wallets()
            elif choice == '5':
                break
            else:
                print("⚠️  Invalid choice. Please enter 1-5.")

    def add_wallet(self) -> None:
        """Add a new tracked wallet."""
        print("\n" + "─"*60)
        print("➕ ADD TRACKED WALLET")
        print("─"*60)

        wallet_address = input("\nWallet address: ").strip()
        if not wallet_address:
            print("❌ Wallet address is required")
            return

        wallet_name = input("Wallet name/nickname: ").strip()
        if not wallet_name:
            wallet_name = wallet_address[:8]

        notes = input("Notes (optional): ").strip()

        wallet_id = self.db.insert_wallet(wallet_address, wallet_name, notes)

        if wallet_id > 0:
            print(f"\n✅ Wallet '{wallet_name}' added successfully!")
        else:
            print(f"\n⚠️  Wallet already exists in database")

    def remove_wallet(self) -> None:
        """Remove a tracked wallet."""
        print("\n" + "─"*60)
        print("❌ REMOVE TRACKED WALLET")
        print("─"*60)

        wallet_address = input("\nWallet address to remove: ").strip()
        if not wallet_address:
            print("❌ Wallet address is required")
            return

        if self.db.remove_wallet(wallet_address):
            print(f"\n✅ Wallet removed successfully!")
        else:
            print(f"\n⚠️  Wallet not found in database")

    def view_all_wallets(self) -> None:
        """View all tracked wallets."""
        print("\n" + "━"*60)
        print("💰 TRACKED SMART MONEY WALLETS")
        print("━"*60)

        wallets = self.db.get_all_wallets()

        if not wallets:
            print("\n⚠️  No tracked wallets yet. Add some to start detecting smart money!")
            return

        print(f"\n📋 Tracking {len(wallets)} wallet(s)\n")
        print(f"{'Tier':<6} {'Name':<20} {'Win Rate':<12} {'Avg Gain':<12} {'Total Buys':<12}")
        print("─"*70)

        for wallet in wallets:
            tier = wallet['tier']
            tier_emoji = get_tier_emoji(tier)
            name = wallet['wallet_name'][:19]
            win_rate = wallet['win_rate'] * 100
            avg_gain = wallet['avg_gain']
            total_buys = wallet['total_tracked_buys']

            print(f"{tier_emoji} {tier:<4} {name:<20} {win_rate:>6.1f}% {avg_gain:>10.0f}% {total_buys:>10}")

        print("\n💡 Tip: Update wallet performance manually using database methods")

    def import_wallets(self) -> None:
        """Import wallets from a JSON file."""
        print("\n" + "─"*60)
        print("📥 IMPORT WALLETS FROM FILE")
        print("─"*60)

        file_path = input("\nFile path (JSON format): ").strip()
        if not file_path:
            print("❌ File path is required")
            return

        try:
            with open(file_path, 'r') as f:
                wallets = json.load(f)

            count = self.db.import_wallets_from_list(wallets)
            print(f"\n✅ Successfully imported {count} wallet(s)")
            print("\nExpected JSON format:")
            print('[')
            print('  {"address": "wallet_address_here", "name": "Wallet Name", "notes": "Optional notes"},')
            print('  {"address": "another_address", "name": "Another Wallet"}')
            print(']')

        except FileNotFoundError:
            print(f"\n❌ File not found: {file_path}")
        except json.JSONDecodeError:
            print(f"\n❌ Invalid JSON format in file")
        except Exception as e:
            print(f"\n❌ Error importing wallets: {e}")

    def add_source_to_existing_token(self) -> None:
        """Add source(s) to an existing token."""
        print("\n" + "━"*60)
        print("➕ ADD SOURCE TO EXISTING TOKEN")
        print("━"*60)

        # Get contract address
        contract_address = input("\nContract address: ").strip()
        if not contract_address:
            print("❌ Contract address is required")
            return

        # Check if token exists
        call = self.db.get_call_by_address(contract_address)
        if not call:
            print(f"\n❌ Token not found in database: {contract_address}")
            print("💡 Tip: Analyze the token first using option [1]")
            return

        # Display current info
        print(f"\n📋 Token: ${call['token_symbol']} - {call['token_name']}")
        print(f"📍 Current source(s): {call['source']}")

        # Get new sources to add
        new_sources_input = input("\nEnter additional source(s) to ADD (comma-separated): ").strip()
        if not new_sources_input:
            print("❌ No sources provided")
            return

        # Parse new sources (normalize to lowercase)
        new_sources = [self.db.normalize_source_name(s) for s in new_sources_input.split(',') if s.strip()]

        # Get existing sources (normalize to lowercase)
        existing_sources = [self.db.normalize_source_name(s) for s in call['source'].split(',') if s.strip()]

        # Merge (avoid duplicates)
        all_sources = existing_sources.copy()
        added_count = 0
        for src in new_sources:
            if src not in all_sources:
                all_sources.append(src)
                added_count += 1
            else:
                print(f"⚠️  Skipping duplicate: {src}")

        if added_count == 0:
            print("\n⚠️  No new sources to add (all were duplicates)")
            return

        # Update database
        updated_source = ', '.join(all_sources)
        self.db.cursor.execute('''
            UPDATE calls_received
            SET source = ?
            WHERE contract_address = ?
        ''', (updated_source, contract_address))
        self.db.conn.commit()

        print(f"\n✅ Added {added_count} new source(s)")
        print(f"📍 Updated source list: {updated_source}")

        # Update source performance for all new sources
        print(f"\n🔄 Updating source performance stats...")
        for src in new_sources:
            if src in all_sources:
                self.db.update_source_performance(src)
        print("✅ Source stats updated")

    def record_exit_trade(self) -> None:
        """Record exit from a trade."""
        print("\n" + "━"*60)
        print("💰 RECORD EXIT")
        print("━"*60)

        # Get open trades
        open_trades = self.db.get_open_trades()

        if not open_trades:
            print("\n⚠️  No open trades to record exit for!")
            return

        # Display open trades
        print(f"\n📋 Open trades ({len(open_trades)}):\n")
        for i, trade in enumerate(open_trades, 1):
            td = trade['timestamp_decision']
            entry_time = td if isinstance(td, datetime) else datetime.fromisoformat(str(td))
            if entry_time.tzinfo is not None:
                entry_time = entry_time.replace(tzinfo=None)
            days_ago = (datetime.now() - entry_time).days
            hours_ago = ((datetime.now() - entry_time).seconds // 3600) if days_ago == 0 else 0

            print(f"[{i}] ${trade['token_symbol']} - {trade['token_name']}")
            print(f"    Entry: ${trade['entry_price']:.10f}" if trade['entry_price'] else "    Entry: N/A")
            print(f"    Size: ${trade['trade_size_usd']:,.2f}" if trade['trade_size_usd'] else "    Size: N/A")
            if days_ago > 0:
                print(f"    Held: {days_ago}d ago")
            else:
                print(f"    Held: {hours_ago}h ago")
            if trade['chart_assessment']:
                print(f"    Chart: {trade['chart_assessment']}")
            print()

        # Get user selection
        try:
            selection = int(input("Select trade number to record exit (or 0 to cancel): ").strip())
            if selection == 0:
                return
            if selection < 1 or selection > len(open_trades):
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Invalid input")
            return

        selected_trade = open_trades[selection - 1]

        # Get exit price
        try:
            exit_price_input = input(f"\n💵 Exit price (current entry: ${selected_trade['entry_price']:.10f}): ").strip()
            exit_price = float(exit_price_input)
        except ValueError:
            print("❌ Invalid exit price")
            return

        # Record the exit
        if self.db.record_exit(selected_trade['call_id'], exit_price):
            entry_price = selected_trade['entry_price']
            pnl_percent = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
            pnl_indicator = "📈" if pnl_percent > 0 else "📉" if pnl_percent < 0 else "➡️"

            print(f"\n✅ Exit recorded successfully!")
            print(f"{pnl_indicator} P&L: {pnl_percent:+.2f}%")

            if selected_trade['trade_size_usd']:
                pnl_usd = selected_trade['trade_size_usd'] * (pnl_percent / 100)
                print(f"💰 P&L (USD): ${pnl_usd:+,.2f}")
        else:
            print("❌ Failed to record exit")

    def run(self) -> None:
        """Main application loop."""
        print_header()

        while True:
            print_menu()
            choice = input("Your choice: ").strip()

            if choice == '1':
                self.analyze_new_call()
            elif choice == '2':
                self.view_source_stats()
            elif choice == '3':
                self.view_watchlist()
            elif choice == '4':
                self.manage_tracked_wallets()
            elif choice == '5':
                self.add_source_to_existing_token()
            elif choice == '6':
                self.view_open_positions()
            elif choice == '7':
                self.convert_watch_to_trade()
            elif choice == '8':
                self.record_exit_trade()
            elif choice == '9':
                self.remove_from_watchlist()
            elif choice == '0':
                print("\n👋 Goodbye! Happy trading!")
                self.db.close()
                sys.exit(0)
            else:
                print("⚠️  Invalid choice. Please enter 0-9.")


def main() -> None:
    """Main entry point."""
    try:
        logger.info("Starting Memecoin Analyzer")
        analyzer = MemecoinAnalyzer()
        analyzer.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("\n\n👋 Interrupted. Goodbye!")
        sys.exit(0)
    except DatabaseError as e:
        logger.error(f"Database error: {e}", exc_info=True)
        print(f"\n❌ Database error: {e.user_message}")
        print("💡 Check if the database file exists and is not corrupted.")
        sys.exit(1)
    except APIError as e:
        logger.error(f"API error: {e}", exc_info=True)
        print(f"\n❌ API error: {e.user_message}")
        print("💡 Check your internet connection and API keys.")
        sys.exit(1)
    except AnalyzerError as e:
        logger.error(f"Analyzer error: {e}", exc_info=True)
        print(f"\n❌ Error: {e.user_message}")
        sys.exit(1)
    except Exception as e:
        # Unexpected error - log full details, show generic message
        logger.exception("Unexpected error occurred")
        print(f"\n❌ An unexpected error occurred: {e}")
        print("💡 Check analyzer.log for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
