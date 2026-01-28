"""
Display and formatting functions for Memecoin Analyzer CLI.

Pure display logic extracted from analyzer.py - no database or API calls.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Type aliases
SafetyRating = tuple[str, str]  # (rating_text, emoji)
TokenData = dict[str, Any]

# =============================================================================
# CONSTANTS
# =============================================================================

TIER_EMOJI: dict[str, str] = {
    'S': '🏆',
    'A': '🥇',
    'B': '🥈',
    'C': '🥉',
}
DEFAULT_TIER_EMOJI = '📊'

SAFETY_THRESHOLDS = {
    'GOOD': 8.0,
    'MODERATE': 6.0,
    'RISKY': 4.0,
}

HONEYPOT_EMOJI = {
    'HIGH': '🚨',
    'MEDIUM': '⚠️',
    'LOW': '✅',
}

PRESSURE_EMOJI = {
    'STRONG BUY': '🟢🟢',
    'BUY': '🟢',
    'NEUTRAL': '⚪',
    'SELL': '🔴',
    'STRONG SELL': '🔴🔴',
}

MOMENTUM_EMOJI = {
    'STRONG UP': '🚀',
    'UP': '📈',
    'NEUTRAL': '➡️',
    'DOWN': '📉',
    'STRONG DOWN': '💥',
}

VOLUME_EMOJI = {
    'VERY HIGH': '🔥',
    'HIGH': '📊',
    'NORMAL': '➡️',
    'LOW': '📉',
    'VERY LOW': '❄️',
}

CONCENTRATION_EMOJI = {
    'CRITICAL': '🔴',
    'HIGH': '🟠',
    'MODERATE': '🟡',
    'LOW': '✅',
    'HEALTHY': '✅',
}


# =============================================================================
# FORMATTING HELPERS
# =============================================================================

def get_safety_rating(score: float) -> SafetyRating:
    """Get safety rating text and emoji based on score.

    Args:
        score: Safety score from 0-10

    Returns:
        Tuple of (rating_text, emoji)
    """
    if score >= SAFETY_THRESHOLDS['GOOD']:
        return "GOOD", "🟢"
    elif score >= SAFETY_THRESHOLDS['MODERATE']:
        return "MODERATE", "🟡"
    elif score >= SAFETY_THRESHOLDS['RISKY']:
        return "RISKY", "🟠"
    else:
        return "DANGEROUS", "🔴"


def format_currency(value: float | None) -> str:
    """Format currency with appropriate suffix (K, M).

    Args:
        value: Dollar amount or None

    Returns:
        Formatted string like "$1.5M" or "N/A"
    """
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.2f}"


def get_tier_emoji(tier: str) -> str:
    """Get emoji for tier rating.

    Args:
        tier: Tier letter (S, A, B, C)

    Returns:
        Emoji string
    """
    return TIER_EMOJI.get(tier, DEFAULT_TIER_EMOJI)


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

def print_header() -> None:
    """Print the main header."""
    print("\n" + "="*60)
    print("🪙  MEMECOIN ANALYZER")
    print("="*60)


def print_menu() -> None:
    """Print the main menu."""
    print("\nOptions:")
    print("  [1] Analyze new call")
    print("  [2] View source stats")
    print("  [3] Watchlist performance")
    print("  [4] Manage tracked wallets")
    print("  [5] Add source to existing token")
    print("  [6] View open positions")
    print("  [7] Convert WATCH to TRADE")
    print("  [8] Record exit")
    print("  [9] Remove from watchlist")
    print("  [0] Exit")
    print()


def display_analysis(symbol: str, name: str, source: str, data: TokenData) -> None:
    """Display the analysis results.

    Args:
        symbol: Token symbol (e.g., "PEPE")
        name: Token name (e.g., "Pepe Coin")
        source: Source of the call
        data: Token data dictionary from fetcher
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("\n" + "━"*60)
    print(f"🪙  TOKEN: ${symbol} ({name})")
    print(f"📍 Source: {source}")
    print(f"⏰ Analyzed: {timestamp}")
    print("━"*60)

    # Safety checks
    safety_score = data.get('safety_score', 0)
    rating, emoji = get_safety_rating(safety_score)

    print(f"\n🔒 SAFETY CHECKS:")
    print(f"{emoji} Safety Score: {safety_score:.1f}/10 ({rating})")

    # Honeypot risk indicator
    honeypot_risk = data.get('honeypot_risk', 'UNKNOWN')
    hp_emoji = HONEYPOT_EMOJI.get(honeypot_risk, '❓')
    if honeypot_risk == 'HIGH':
        print(f"{hp_emoji} Honeypot Risk: HIGH - May not be sellable!")
    elif honeypot_risk == 'MEDIUM':
        print(f"{hp_emoji}  Honeypot Risk: MEDIUM - Proceed with caution")
    elif honeypot_risk == 'LOW':
        print(f"{hp_emoji} Honeypot Risk: LOW")

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

    # Token taxes
    buy_tax = data.get('estimated_buy_tax', 0)
    sell_tax = data.get('estimated_sell_tax', 0)
    if buy_tax > 0 or sell_tax > 0:
        tax_emoji = "🔴" if sell_tax > 10 else "🟡" if sell_tax > 5 else "✅"
        print(f"{tax_emoji} Token Taxes: Buy {buy_tax:.0f}% / Sell {sell_tax:.0f}%")

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

    # Holder distribution
    holder_concentration = data.get('holder_concentration')
    if holder_concentration:
        conc_emoji = CONCENTRATION_EMOJI.get(holder_concentration, '⚪')
        top_5_pct = data.get('top_5_pct', 0)
        whale_count = data.get('whale_count', 0)
        print(f"{conc_emoji} Distribution: {holder_concentration} (Top 5: {top_5_pct:.0f}%, {whale_count} whales)")

    # Smart money detection
    smart_money_wallets = data.get('smart_money_wallets', [])
    if smart_money_wallets:
        print(f"\n💰 SMART MONEY DETECTED:")
        for wallet in smart_money_wallets:
            tier = wallet['tier']
            tier_emoji_sm = {'S': '🟢', 'A': '🟢', 'B': '🟡', 'C': '🟠'}.get(tier, '⚪')
            win_rate_pct = wallet['win_rate'] * 100
            avg_gain_pct = wallet['avg_gain']
            print(f"{tier_emoji_sm} Wallet: {wallet['wallet_name']} ({tier}-Tier, {win_rate_pct:.0f}% win rate, avg +{avg_gain_pct:.0f}%)")
            logger.info(f"Smart money detected: {wallet['wallet_name']} tier={tier}")

        if len(smart_money_wallets) > 2:
            others = len(smart_money_wallets) - 2
            if others > 0:
                print(f"🟡 +{others} other profitable wallet(s) holding")

        smart_bonus = data.get('smart_money_bonus', 0)
        if smart_bonus > 0:
            print(f"✨ Safety score bonus: +{smart_bonus:.1f} points")

    # Market data
    print(f"\n📊 MARKET DATA:")

    # Display liquidity (with pool breakdown if available)
    main_pool_liq = data.get('main_pool_liquidity')
    total_liq = data.get('total_liquidity')
    main_pool_dex = data.get('main_pool_dex')

    if main_pool_liq and total_liq and main_pool_dex:
        # Show detailed pool breakdown
        print(f"💧 Main Pool ({main_pool_dex}): {format_currency(main_pool_liq)}")
        if total_liq > main_pool_liq:
            print(f"💧 Total Liquidity: {format_currency(total_liq)}")
    else:
        # Fallback to old format
        liquidity = data.get('liquidity_usd', 0)
        print(f"💧 Liquidity: {format_currency(liquidity)}")

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
    print(f"📈 24h Volume: {format_currency(volume)}")

    # Volume/Liquidity ratio
    liquidity_val = data.get('liquidity_usd', 0)
    if liquidity_val and liquidity_val > 0 and volume:
        vol_liq = volume / liquidity_val
        vl_emoji = "🔥" if vol_liq > 2.0 else "📊" if vol_liq > 1.0 else "➡️" if vol_liq > 0.3 else "📉"
        print(f"{vl_emoji} Vol/Liq Ratio: {vol_liq:.2f}x")

    market_cap = data.get('market_cap')
    if market_cap:
        print(f"💰 Market Cap: {format_currency(market_cap)}")

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

    # Momentum indicators
    momentum_score = data.get('momentum_score')
    if momentum_score is not None:
        print(f"\n📊 MOMENTUM ANALYSIS:")

        # Overall momentum score
        mom_emoji = "🚀" if momentum_score >= 7 else "📈" if momentum_score >= 5.5 else "📉" if momentum_score < 4 else "➡️"
        print(f"{mom_emoji} Momentum Score: {momentum_score:.1f}/10")

        # Buy/sell pressure
        pressure = data.get('buy_sell_pressure', 'NEUTRAL')
        pressure_emoji = PRESSURE_EMOJI.get(pressure, '⚪')
        print(f"{pressure_emoji} Buy/Sell Pressure: {pressure}")

        # Price momentum
        price_mom = data.get('price_momentum', 'NEUTRAL')
        price_emoji = MOMENTUM_EMOJI.get(price_mom, '➡️')
        print(f"{price_emoji} Price Momentum: {price_mom}")

        # Volume trend
        vol_trend = data.get('volume_trend', 'UNKNOWN')
        vol_emoji = VOLUME_EMOJI.get(vol_trend, '❓')
        print(f"{vol_emoji} Volume Trend: {vol_trend}")

    # Red flags
    red_flags = data.get('red_flags', [])
    if red_flags:
        print(f"\n⚠️  RED FLAGS:")
        for flag in red_flags:
            print(f"   {flag}")
    else:
        print(f"\n✅ No major red flags detected!")
