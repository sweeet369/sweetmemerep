#!/usr/bin/env python3
"""
Memecoin Trading Analyzer - Main CLI Interface
"""

import sys
from datetime import datetime
from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher


class MemecoinAnalyzer:
    """Main CLI interface for memecoin analysis."""

    def __init__(self):
        """Initialize analyzer with database and data fetcher."""
        self.db = MemecoinDatabase()
        self.fetcher = MemecoinDataFetcher()

    def print_header(self):
        """Print the main header."""
        print("\n" + "="*60)
        print("🪙  MEMECOIN ANALYZER")
        print("="*60)

    def print_menu(self):
        """Print the main menu."""
        print("\nOptions:")
        print("  [1] Analyze new call")
        print("  [2] View source stats")
        print("  [3] Watchlist performance")
        print("  [4] Manage tracked wallets")
        print("  [5] Add source to existing token")
        print("  [6] Record exit")
        print("  [7] Remove from watchlist")
        print("  [8] Convert WATCH to TRADE")
        print("  [9] Exit")
        print()

    def get_safety_rating(self, score: float) -> tuple:
        """Get safety rating text and emoji based on score."""
        if score >= 8.0:
            return "GOOD", "🟢"
        elif score >= 6.0:
            return "MODERATE", "🟡"
        elif score >= 4.0:
            return "RISKY", "🟠"
        else:
            return "DANGEROUS", "🔴"

    def format_currency(self, value: float) -> str:
        """Format currency with appropriate suffix."""
        if value is None:
            return "N/A"
        if value >= 1_000_000:
            return f"${value/1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value/1_000:.1f}K"
        else:
            return f"${value:.2f}"

    def analyze_new_call(self):
        """Analyze a new memecoin call."""
        print("\n" + "━"*60)
        print("📞 NEW CALL ANALYSIS")
        print("━"*60)

        # Get contract address
        contract_address = input("\nContract address: ").strip()
        if not contract_address:
            print("❌ Contract address is required")
            return

        # Get source(s) - allow comma-separated
        source_input = input("Source name(s) - comma-separated for multiple (e.g., 'Alpha Group #3, Twitter Call'): ").strip()
        if not source_input:
            source = "Unknown"
        else:
            # Clean up sources: split by comma, strip whitespace, remove empties
            sources = [s.strip() for s in source_input.split(',') if s.strip()]
            source = ', '.join(sources)  # Store as comma-separated string

        # Get blockchain
        blockchain = input("Blockchain [Solana/BNB] (default Solana): ").strip()
        if not blockchain:
            blockchain = "Solana"

        print(f"\n⏳ Fetching data for {contract_address}...")
        print("━"*60)

        # Get tracked wallets for smart money detection
        tracked_wallets = self.db.get_all_wallets()

        # Fetch data (with smart money detection)
        data = self.fetcher.fetch_all_data(contract_address, tracked_wallets=tracked_wallets)

        if not data:
            print("\n❌ Failed to fetch token data. Token may not exist or APIs are unavailable.")
            return

        # Get token info from DexScreener raw data
        token_name = "Unknown"
        token_symbol = "Unknown"
        if data.get('raw_data', {}).get('dexscreener'):
            dex_raw = data['raw_data']['dexscreener']
            token_name = dex_raw.get('baseToken', {}).get('name', 'Unknown')
            token_symbol = dex_raw.get('baseToken', {}).get('symbol', 'Unknown')

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
        self.display_analysis(token_symbol, token_name, source, data)

        # Get user decision
        self.get_user_decision(call_id, contract_address, data)

        # Update source performance for all sources
        sources = [s.strip() for s in source.split(',')]
        for src in sources:
            self.db.update_source_performance(src)

        print(f"\n✅ Saved to database (Call ID: {call_id})")

    def display_analysis(self, symbol: str, name: str, source: str, data: dict):
        """Display the analysis results."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        print("\n" + "━"*60)
        print(f"🪙  TOKEN: ${symbol} ({name})")
        print(f"📍 Source: {source}")
        print(f"⏰ Analyzed: {timestamp}")
        print("━"*60)

        # Safety checks
        safety_score = data.get('safety_score', 0)
        rating, emoji = self.get_safety_rating(safety_score)

        print(f"\n🔒 SAFETY CHECKS:")
        print(f"{emoji} Safety Score: {safety_score:.1f}/10 ({rating})")

        mint_revoked = data.get('mint_authority_revoked')
        freeze_revoked = data.get('freeze_authority_revoked')

        if mint_revoked == 1:
            print("✅ Mint Authority: REVOKED")
        elif mint_revoked == 0:
            print("❌ Mint Authority: ACTIVE")
        else:
            print("⚠️  Mint Authority: UNKNOWN")

        if freeze_revoked == 1:
            print("✅ Freeze Authority: REVOKED")
        elif freeze_revoked == 0:
            print("❌ Freeze Authority: ACTIVE")
        else:
            print("⚠️  Freeze Authority: UNKNOWN")

        top_holder = data.get('top_holder_percent')
        if top_holder is not None:
            if top_holder > 20:
                print(f"🔴 Top Holder: {top_holder:.1f}% (HIGH RISK)")
            elif top_holder > 15:
                print(f"🟡 Top Holder: {top_holder:.1f}% (moderate risk)")
            else:
                print(f"✅ Top Holder: {top_holder:.1f}% (acceptable)")
        else:
            print("⚠️  Top Holder: N/A")

        # Smart money detection
        smart_money_wallets = data.get('smart_money_wallets', [])
        if smart_money_wallets:
            print(f"\n💰 SMART MONEY DETECTED:")
            for wallet in smart_money_wallets:
                tier = wallet['tier']
                tier_emoji = {'S': '🟢', 'A': '🟢', 'B': '🟡', 'C': '🟠'}.get(tier, '⚪')
                win_rate_pct = wallet['win_rate'] * 100
                avg_gain_pct = wallet['avg_gain']
                print(f"{tier_emoji} Wallet: {wallet['wallet_name']} ({tier}-Tier, {win_rate_pct:.0f}% win rate, avg +{avg_gain_pct:.0f}%)")

            if len(smart_money_wallets) > 2:
                others = len(smart_money_wallets) - 2
                if others > 0:
                    print(f"🟡 +{others} other profitable wallet(s) holding")

            smart_bonus = data.get('smart_money_bonus', 0)
            if smart_bonus > 0:
                print(f"✨ Safety score bonus: +{smart_money_bonus:.1f} points")

        # Market data
        print(f"\n📊 MARKET DATA:")

        # Display liquidity (with pool breakdown if available)
        main_pool_liq = data.get('main_pool_liquidity')
        total_liq = data.get('total_liquidity')
        main_pool_dex = data.get('main_pool_dex')

        if main_pool_liq and total_liq and main_pool_dex:
            # Show detailed pool breakdown
            print(f"💧 Main Pool ({main_pool_dex}): {self.format_currency(main_pool_liq)}")
            if total_liq > main_pool_liq:
                print(f"💧 Total Liquidity: {self.format_currency(total_liq)}")
        else:
            # Fallback to old format
            liquidity = data.get('liquidity_usd', 0)
            print(f"💧 Liquidity: {self.format_currency(liquidity)}")

        holders = data.get('holder_count')
        if holders is not None and holders > 0:
            print(f"👥 Holders: {holders:,}")
        else:
            print(f"👥 Holders: N/A")

        token_age = data.get('token_age_hours', 0)
        if token_age >= 24:
            print(f"⏰ Age: {token_age/24:.1f} days")
        else:
            print(f"⏰ Age: {token_age:.1f} hours")

        volume = data.get('volume_24h', 0)
        print(f"📈 24h Volume: {self.format_currency(volume)}")

        market_cap = data.get('market_cap')
        if market_cap:
            print(f"💰 Market Cap: {self.format_currency(market_cap)}")

        price = data.get('price_usd')
        if price:
            print(f"💵 Price: ${price:.10f}")

        # Price changes
        price_change_5m = data.get('price_change_5m')
        price_change_1h = data.get('price_change_1h')
        price_change_24h = data.get('price_change_24h')

        if any([price_change_5m, price_change_1h, price_change_24h]):
            print(f"\n📈 PRICE CHANGES:")
            if price_change_5m is not None:
                indicator = "📈" if price_change_5m > 0 else "📉" if price_change_5m < 0 else "➡️"
                print(f"{indicator} 5m: {price_change_5m:+.2f}%")
            if price_change_1h is not None:
                indicator = "📈" if price_change_1h > 0 else "📉" if price_change_1h < 0 else "➡️"
                print(f"{indicator} 1h: {price_change_1h:+.2f}%")
            if price_change_24h is not None:
                indicator = "📈" if price_change_24h > 0 else "📉" if price_change_24h < 0 else "➡️"
                print(f"{indicator} 24h: {price_change_24h:+.2f}%")

        # Buy/Sell activity
        buy_count = data.get('buy_count_24h')
        sell_count = data.get('sell_count_24h')
        if buy_count is not None and sell_count is not None:
            total_txns = buy_count + sell_count
            buy_ratio = (buy_count / total_txns * 100) if total_txns > 0 else 0
            print(f"\n💱 24H ACTIVITY:")
            print(f"🟢 Buys: {buy_count} ({buy_ratio:.1f}%)")
            print(f"🔴 Sells: {sell_count} ({100-buy_ratio:.1f}%)")

        # Red flags
        red_flags = data.get('red_flags', [])
        if red_flags:
            print(f"\n⚠️  RED FLAGS:")
            for flag in red_flags:
                print(f"   {flag}")
        else:
            print(f"\n✅ No major red flags detected!")

    def get_user_decision(self, call_id: int, contract_address: str, data: dict):
        """Get and record user's trading decision."""
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
            current_data = self.fetcher.fetch_dexscreener_data(contract_address)
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

    def view_source_stats(self):
        """Display statistics for all sources."""
        print("\n" + "━"*60)
        print("📊 SOURCE PERFORMANCE STATISTICS")
        print("━"*60)

        sources = self.db.get_all_sources()

        if not sources:
            print("\n⚠️  No source data available yet. Analyze some calls first!")
            return

        print(f"\n{'Tier':<6} {'Source':<25} {'Calls':<8} {'Traded':<8} {'Win%':<8} {'Hit%':<8} {'Avg Gain':<12} {'Rug%':<8}")
        print("─"*95)

        for source in sources:
            tier = source['tier']
            name = source['source_name'][:24]
            total = source['total_calls']
            traded = source['calls_traded']
            win_rate = source['win_rate'] * 100
            hit_rate = source.get('hit_rate', 0.0) * 100  # Get hit_rate, default to 0
            avg_gain = source['avg_max_gain']
            rug_rate = source['rug_rate'] * 100

            # Add tier emoji
            tier_emoji = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉'}.get(tier, '📊')

            print(f"{tier_emoji} {tier:<4} {name:<25} {total:<8} {traded:<8} {win_rate:>6.1f}% {hit_rate:>6.1f}% {avg_gain:>10.1f}% {rug_rate:>6.1f}%")

    def view_watchlist(self):
        """Display performance of all tokens in watchlist."""
        print("\n" + "━"*60)
        print("👀 WATCHLIST PERFORMANCE")
        print("━"*60)

        # Query all WATCH decisions with token data
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
                d.timestamp_decision,
                d.reasoning_notes,
                d.confidence_level,
                p.current_mcap,
                p.current_liquidity,
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
            # Header for each token
            print("─"*60)
            print(f"[{i}] ${token['token_symbol']} - {token['token_name']}")
            print(f"    📍 Source: {token['source']}")
            print(f"    🔗 {token['contract_address'][:20]}...")

            # Safety and entry info
            safety_score = token['safety_score'] or 0
            rating, emoji = self.get_safety_rating(safety_score)
            print(f"    {emoji} Safety Score: {safety_score:.1f}/10 ({rating})")
            print(f"    💧 Entry Liquidity: {self.format_currency(token['entry_liquidity'])}")

            # Market cap info
            initial_mcap = token.get('initial_mcap')
            current_mcap = token.get('current_mcap')
            if initial_mcap:
                print(f"    💰 Initial MCap: {self.format_currency(initial_mcap)}")
            if current_mcap:
                mcap_change = ((current_mcap - initial_mcap) / initial_mcap * 100) if initial_mcap else 0
                mcap_indicator = "📈" if mcap_change > 0 else "📉" if mcap_change < 0 else "➡️"
                print(f"    {mcap_indicator} Current MCap: {self.format_currency(current_mcap)} ({mcap_change:+.1f}%)")

            # Liquidity tracking
            entry_liquidity = token.get('entry_liquidity')
            current_liquidity = token.get('current_liquidity')
            if current_liquidity and entry_liquidity:
                liq_change = ((current_liquidity - entry_liquidity) / entry_liquidity * 100) if entry_liquidity else 0
                liq_indicator = "📈" if liq_change > 0 else "📉" if liq_change < 0 else "➡️"
                print(f"    {liq_indicator} Current Liquidity: {self.format_currency(current_liquidity)} ({liq_change:+.1f}%)")

            # Decision info
            from datetime import datetime
            decision_time = datetime.fromisoformat(token['timestamp_decision'])
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

                if token['last_updated']:
                    update_time = datetime.fromisoformat(token['last_updated'])
                    update_mins_ago = (datetime.now() - update_time).seconds // 60
                    print(f"    🔄 Last updated: {update_mins_ago}m ago")
            else:
                print(f"    ⏳ Waiting for performance data...")
                print(f"    💡 Run: python3 performance_tracker.py")

        print("─"*60)
        print(f"\n💡 Tip: Tokens showing strong gains may be good entry opportunities!")
        print(f"💡 To remove from watchlist, use option [7] Remove from watchlist")

    def convert_watch_to_trade(self):
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
        current_data = self.fetcher.fetch_dexscreener_data(contract_address)

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

    def remove_from_watchlist(self):
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

    def manage_tracked_wallets(self):
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

    def add_wallet(self):
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

    def remove_wallet(self):
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

    def view_all_wallets(self):
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
            tier_emoji = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉'}.get(tier, '📊')
            name = wallet['wallet_name'][:19]
            win_rate = wallet['win_rate'] * 100
            avg_gain = wallet['avg_gain']
            total_buys = wallet['total_tracked_buys']

            print(f"{tier_emoji} {tier:<4} {name:<20} {win_rate:>6.1f}% {avg_gain:>10.0f}% {total_buys:>10}")

        print("\n💡 Tip: Update wallet performance manually using database methods")

    def import_wallets(self):
        """Import wallets from a JSON file."""
        print("\n" + "─"*60)
        print("📥 IMPORT WALLETS FROM FILE")
        print("─"*60)

        file_path = input("\nFile path (JSON format): ").strip()
        if not file_path:
            print("❌ File path is required")
            return

        try:
            import json
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

    def add_source_to_existing_token(self):
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

        # Parse new sources
        new_sources = [s.strip() for s in new_sources_input.split(',') if s.strip()]

        # Get existing sources
        existing_sources = [s.strip() for s in call['source'].split(',') if s.strip()]

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

    def record_exit_trade(self):
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
            from datetime import datetime
            entry_time = datetime.fromisoformat(trade['timestamp_decision'])
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

    def run(self):
        """Main application loop."""
        self.print_header()

        while True:
            self.print_menu()
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
                self.record_exit_trade()
            elif choice == '7':
                self.remove_from_watchlist()
            elif choice == '8':
                self.convert_watch_to_trade()
            elif choice == '9':
                print("\n👋 Goodbye! Happy trading!")
                self.db.close()
                sys.exit(0)
            else:
                print("⚠️  Invalid choice. Please enter 1-9.")


def main():
    """Main entry point."""
    try:
        analyzer = MemecoinAnalyzer()
        analyzer.run()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
