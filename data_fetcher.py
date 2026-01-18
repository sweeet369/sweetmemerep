import requests
import time
from datetime import datetime
from typing import Dict, Any, Optional, List


class MemecoinDataFetcher:
    """Fetches memecoin data from DexScreener and RugCheck APIs."""

    DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens/{address}"
    RUGCHECK_API = "https://api.rugcheck.xyz/v1/tokens/{address}/report"

    def __init__(self, timeout: int = 10, retry_attempts: int = 1):
        """Initialize data fetcher with timeout and retry settings."""
        self.timeout = timeout
        self.retry_attempts = retry_attempts

    def fetch_dexscreener_data(self, address: str) -> Optional[Dict[str, Any]]:
        """Fetch market data from DexScreener API."""
        url = self.DEXSCREENER_API.format(address=address)

        for attempt in range(self.retry_attempts + 1):
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                if not data.get('pairs') or len(data['pairs']) == 0:
                    return None

                # Get all pairs and sort by liquidity
                pairs = sorted(data['pairs'], key=lambda x: x.get('liquidity', {}).get('usd', 0), reverse=True)
                main_pair = pairs[0]

                # Calculate liquidity across all pools
                main_pool_liquidity = float(main_pair.get('liquidity', {}).get('usd', 0))
                total_liquidity = sum(float(pair.get('liquidity', {}).get('usd', 0)) for pair in pairs)
                main_pool_dex = main_pair.get('dexId', 'Unknown')

                # Extract price changes for different timeframes
                price_change = main_pair.get('priceChange', {})

                # Extract liquidity info (backward compatibility - use main pool)
                liquidity_usd = main_pool_liquidity

                # Try to get ATH/ATL if available (not always present)
                price_usd = float(main_pair.get('priceUsd', 0))

                return {
                    'price_usd': price_usd,
                    'liquidity_usd': liquidity_usd,  # Backward compatibility
                    'main_pool_liquidity': main_pool_liquidity,
                    'total_liquidity': total_liquidity,
                    'main_pool_dex': main_pool_dex,
                    'volume_24h': float(main_pair.get('volume', {}).get('h24', 0)),
                    'market_cap': float(main_pair.get('fdv', 0)),
                    'price_change_5m': float(price_change.get('m5', 0)) if price_change.get('m5') else None,
                    'price_change_1h': float(price_change.get('h1', 0)) if price_change.get('h1') else None,
                    'price_change_24h': float(price_change.get('h24', 0)) if price_change.get('h24') else None,
                    'pair_created_at': main_pair.get('pairCreatedAt'),
                    'txns_24h_buys': main_pair.get('txns', {}).get('h24', {}).get('buys', 0),
                    'txns_24h_sells': main_pair.get('txns', {}).get('h24', {}).get('sells', 0),
                    'dex': main_pair.get('dexId'),
                    'pair_address': main_pair.get('pairAddress'),
                    'raw_data': main_pair
                }

            except requests.exceptions.Timeout:
                if attempt < self.retry_attempts:
                    time.sleep(1)
                    continue
                print(f"⚠️  DexScreener API timeout after {self.retry_attempts + 1} attempts")
                return None
            except requests.exceptions.RequestException as e:
                print(f"⚠️  DexScreener API error: {e}")
                return None
            except (KeyError, ValueError) as e:
                print(f"⚠️  Error parsing DexScreener data: {e}")
                return None

        return None

    def fetch_rugcheck_data(self, address: str) -> Optional[Dict[str, Any]]:
        """Fetch security data from RugCheck API."""
        url = self.RUGCHECK_API.format(address=address)

        for attempt in range(self.retry_attempts + 1):
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                # Parse mint and freeze authority
                mint_revoked = data.get('mintAuthority') is None or data.get('mintAuthority') == 'null'
                freeze_revoked = data.get('freezeAuthority') is None or data.get('freezeAuthority') == 'null'

                # Parse top holders
                top_holders = data.get('topHolders') or []
                top_holder_percent = float(top_holders[0].get('pct', 0)) if top_holders else 0.0
                top_10_percent = sum(float(h.get('pct', 0)) for h in top_holders[:10]) if top_holders else 0.0

                # Get holder count
                holder_count = data.get('markets', [{}])[0].get('holder', 0) if data.get('markets') else 0

                # Get rugcheck score
                rugcheck_score = float(data.get('score', 0))

                return {
                    'mint_authority_revoked': mint_revoked,
                    'freeze_authority_revoked': freeze_revoked,
                    'top_holder_percent': top_holder_percent,
                    'top_10_holders_percent': top_10_percent,
                    'holder_count': holder_count,
                    'rugcheck_score': rugcheck_score,
                    'raw_data': data
                }

            except requests.exceptions.Timeout:
                if attempt < self.retry_attempts:
                    time.sleep(1)
                    continue
                print(f"⚠️  RugCheck API timeout after {self.retry_attempts + 1} attempts")
                return None
            except requests.exceptions.RequestException as e:
                print(f"⚠️  RugCheck API error: {e}")
                return None
            except (KeyError, ValueError) as e:
                print(f"⚠️  Error parsing RugCheck data: {e}")
                return None

        return None

    def calculate_token_age_hours(self, pair_created_timestamp: Optional[int]) -> float:
        """Calculate token age in hours from pair creation timestamp."""
        if not pair_created_timestamp:
            return 0.0

        created_time = datetime.fromtimestamp(pair_created_timestamp / 1000)
        age = datetime.now() - created_time
        return age.total_seconds() / 3600

    def detect_red_flags(self, data: Dict[str, Any]) -> List[str]:
        """Detect red flags in the token data."""
        red_flags = []

        liquidity = data.get('liquidity_usd', 0)
        mint_revoked = data.get('mint_authority_revoked', False)
        freeze_revoked = data.get('freeze_authority_revoked', False)
        top_holder = data.get('top_holder_percent', 0)
        token_age = data.get('token_age_hours', 0)
        volume = data.get('volume_24h', 0)

        # Critical flags
        if liquidity < 20000:
            red_flags.append(f"🔴 CRITICAL: Low liquidity (${liquidity:,.0f})")

        if not mint_revoked:
            red_flags.append("🔴 CRITICAL: Mint authority NOT revoked")

        if not freeze_revoked:
            red_flags.append("🔴 CRITICAL: Freeze authority active")

        # High risk flags
        if top_holder > 20:
            red_flags.append(f"🟠 HIGH RISK: Top holder owns {top_holder:.1f}%")

        # Medium risk flags
        if token_age < 0.5:
            red_flags.append(f"🟡 MEDIUM: Very new token ({token_age:.1f}h old)")

        if liquidity > 0 and (volume / liquidity) < 0.05:
            red_flags.append(f"🟡 MEDIUM: Low trading activity (V/L ratio: {volume/liquidity:.3f})")

        return red_flags

    def calculate_safety_score(self, data: Dict[str, Any]) -> float:
        """Calculate safety score (0-10) based on various factors."""
        score = 10.0

        liquidity = data.get('liquidity_usd', 0)
        mint_revoked = data.get('mint_authority_revoked', False)
        freeze_revoked = data.get('freeze_authority_revoked', False)
        top_holder = data.get('top_holder_percent', 0)
        token_age = data.get('token_age_hours', 0)
        volume = data.get('volume_24h', 0)

        # Critical deductions
        if liquidity < 20000:
            score -= 3.0
        if not mint_revoked:
            score -= 3.0
        if not freeze_revoked:
            score -= 3.0

        # High risk deductions
        if top_holder > 20:
            score -= 2.0
        elif top_holder > 15:
            score -= 1.0

        # Medium risk deductions
        if token_age < 0.5:
            score -= 1.0

        if liquidity > 0 and (volume / liquidity) < 0.05:
            score -= 1.0

        # Bonus points
        if liquidity > 100000:
            score += 0.5

        # Ensure score is between 0 and 10
        return max(0.0, min(10.0, score))

    def check_smart_money_wallets(self, top_holders: List[Dict], tracked_wallets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Cross-reference top holders with tracked smart money wallets.

        Args:
            top_holders: List of top holder dicts from RugCheck (with 'address' and 'pct' keys)
            tracked_wallets: List of tracked wallet dicts from database

        Returns:
            List of matched wallets with their performance stats
        """
        matches = []

        if not top_holders or not tracked_wallets:
            return matches

        # Create a map of tracked wallet addresses for fast lookup
        tracked_map = {w['wallet_address'].lower(): w for w in tracked_wallets}

        # Check each top holder
        for holder in top_holders:
            holder_address = holder.get('address', '').lower()
            if holder_address in tracked_map:
                wallet_info = tracked_map[holder_address]
                matches.append({
                    'wallet_address': wallet_info['wallet_address'],
                    'wallet_name': wallet_info['wallet_name'],
                    'tier': wallet_info['tier'],
                    'win_rate': wallet_info['win_rate'],
                    'avg_gain': wallet_info['avg_gain'],
                    'total_buys': wallet_info['total_tracked_buys'],
                    'holding_percent': holder.get('pct', 0)
                })

        return matches

    def fetch_all_data(self, address: str, tracked_wallets: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch and combine data from all sources."""
        print(f"🔍 Fetching DexScreener data...")
        dex_data = self.fetch_dexscreener_data(address)

        if not dex_data:
            print("❌ Failed to fetch DexScreener data or token not found")
            return None

        print(f"🔍 Fetching RugCheck data...")
        rug_data = self.fetch_rugcheck_data(address)

        # Combine all data
        combined_data = {}

        # DexScreener data
        if dex_data:
            combined_data.update({
                'liquidity_usd': dex_data['liquidity_usd'],
                'main_pool_liquidity': dex_data.get('main_pool_liquidity'),
                'total_liquidity': dex_data.get('total_liquidity'),
                'main_pool_dex': dex_data.get('main_pool_dex'),
                'volume_24h': dex_data['volume_24h'],
                'price_usd': dex_data['price_usd'],
                'market_cap': dex_data['market_cap'],
                'token_age_hours': self.calculate_token_age_hours(dex_data.get('pair_created_at')),
                'price_change_5m': dex_data.get('price_change_5m'),
                'price_change_1h': dex_data.get('price_change_1h'),
                'price_change_24h': dex_data.get('price_change_24h'),
                'buy_count_24h': dex_data.get('txns_24h_buys'),
                'sell_count_24h': dex_data.get('txns_24h_sells'),
                # ATH/ATL and liquidity locked data not available in basic API
                'all_time_high': None,
                'all_time_low': None,
                'price_vs_atl_percent': None,
                'liquidity_locked_percent': None,
            })

        # RugCheck data
        if rug_data:
            combined_data.update({
                'holder_count': rug_data['holder_count'],
                'top_holder_percent': rug_data['top_holder_percent'],
                'top_10_holders_percent': rug_data['top_10_holders_percent'],
                'mint_authority_revoked': 1 if rug_data['mint_authority_revoked'] else 0,
                'freeze_authority_revoked': 1 if rug_data['freeze_authority_revoked'] else 0,
                'rugcheck_score': rug_data['rugcheck_score'],
            })
        else:
            # Set defaults if RugCheck fails
            combined_data.update({
                'holder_count': None,
                'top_holder_percent': None,
                'top_10_holders_percent': None,
                'mint_authority_revoked': None,
                'freeze_authority_revoked': None,
                'rugcheck_score': None,
            })

        # Check for smart money wallets
        smart_money_wallets = []
        smart_money_bonus = 0
        if tracked_wallets and rug_data and rug_data.get('raw_data', {}).get('topHolders'):
            top_holders = rug_data['raw_data'].get('topHolders', [])
            smart_money_wallets = self.check_smart_money_wallets(top_holders, tracked_wallets)

            # Calculate smart money bonus for safety score
            wallet_count = len(smart_money_wallets)
            if wallet_count >= 3:
                smart_money_bonus = 2.0  # 20 points converted to 2.0 on 0-10 scale
            elif wallet_count >= 1:
                smart_money_bonus = 1.0  # 10 points converted to 1.0 on 0-10 scale

        combined_data['smart_money_wallets'] = smart_money_wallets
        combined_data['smart_money_count'] = len(smart_money_wallets)

        # Calculate safety score (base score)
        base_safety_score = self.calculate_safety_score(combined_data)

        # Add smart money bonus (capped at 10.0)
        combined_data['safety_score'] = min(10.0, base_safety_score + smart_money_bonus)
        combined_data['smart_money_bonus'] = smart_money_bonus

        # Detect red flags
        combined_data['red_flags'] = self.detect_red_flags(combined_data)

        # Store raw data
        combined_data['raw_data'] = {
            'dexscreener': dex_data.get('raw_data', {}),
            'rugcheck': rug_data.get('raw_data', {}) if rug_data else {}
        }

        return combined_data


if __name__ == "__main__":
    # Test with BONK token
    print("Testing MemecoinDataFetcher with BONK token...")
    print("=" * 60)

    fetcher = MemecoinDataFetcher()
    address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

    data = fetcher.fetch_all_data(address)

    if data:
        print("\n✅ Data fetched successfully!")
        print("\n📊 MARKET DATA:")
        print(f"   Price: ${data.get('price_usd', 0):.8f}")
        print(f"   Liquidity: ${data.get('liquidity_usd', 0):,.2f}")
        print(f"   24h Volume: ${data.get('volume_24h', 0):,.2f}")
        print(f"   Market Cap: ${data.get('market_cap', 0):,.2f}")
        print(f"   Token Age: {data.get('token_age_hours', 0):.1f} hours")

        print("\n🔒 SECURITY DATA:")
        print(f"   Holders: {data.get('holder_count', 'N/A')}")
        print(f"   Top Holder: {data.get('top_holder_percent', 0):.2f}%")
        print(f"   Mint Revoked: {'✅' if data.get('mint_authority_revoked') else '❌'}")
        print(f"   Freeze Revoked: {'✅' if data.get('freeze_authority_revoked') else '❌'}")
        print(f"   RugCheck Score: {data.get('rugcheck_score', 'N/A')}")

        print(f"\n🎯 SAFETY SCORE: {data.get('safety_score', 0):.1f}/10")

        if data.get('red_flags'):
            print("\n⚠️  RED FLAGS:")
            for flag in data['red_flags']:
                print(f"   {flag}")
        else:
            print("\n✅ No major red flags detected!")

    else:
        print("\n❌ Failed to fetch data")
