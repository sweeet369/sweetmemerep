import random
import requests
import time
from datetime import datetime, timedelta
from functools import wraps, lru_cache
from typing import Dict, Any, Optional, List, Callable, TypeVar

# Import structured logging
from app_logger import api_logger, log_api_call

# Import centralized config
from config import BIRDEYE_API_KEY

# Type variable for generic return types
T = TypeVar('T')


# =============================================================================
# CACHING - Simple TTL cache for API responses
# =============================================================================

class TTLCache:
    """Simple time-to-live cache for API responses."""
    
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        cached = self._cache[key]
        if datetime.now() - cached['timestamp'] > timedelta(seconds=self.ttl):
            del self._cache[key]
            return None
        return cached['data']
    
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Set cached value with timestamp."""
        self._cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count cleaned."""
        now = datetime.now()
        expired = [
            k for k, v in self._cache.items()
            if now - v['timestamp'] > timedelta(seconds=self.ttl)
        ]
        for k in expired:
            del self._cache[k]
        return len(expired)


# Global cache for API responses (60 second TTL)
_api_cache = TTLCache(ttl_seconds=60)


def get_api_cache() -> TTLCache:
    """Get the global API cache instance."""
    return _api_cache


# =============================================================================
# ERROR CLASSES - Typed errors for better handling
# =============================================================================

class APIError(Exception):
    """Base class for all API errors."""
    is_transient = False

    def __init__(self, message: str, source: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.source = source  # 'birdeye', 'goplus'
        self.cause = cause


class NetworkError(APIError):
    """Network-level errors (connection refused, DNS failures, etc.)."""
    is_transient = True


class TimeoutError(APIError):
    """Request timed out - usually transient."""
    is_transient = True


class RateLimitError(APIError):
    """Rate limit exceeded (429)."""
    is_transient = True

    def __init__(self, message: str, source: str, retry_after: Optional[int] = None):
        super().__init__(message, source)
        self.retry_after = retry_after or 60  # Default to 60 seconds


class ServerError(APIError):
    """Server-side errors (5xx) - often transient."""
    is_transient = True

    def __init__(self, message: str, source: str, status_code: int):
        super().__init__(message, source)
        self.status_code = status_code


class ClientError(APIError):
    """Client-side errors (4xx except 429) - NOT transient, don't retry."""
    is_transient = False

    def __init__(self, message: str, source: str, status_code: int):
        super().__init__(message, source)
        self.status_code = status_code


class ParseError(APIError):
    """Failed to parse API response - NOT transient."""
    is_transient = False


class NoDataError(APIError):
    """API returned successfully but no data found - NOT transient."""
    is_transient = False


# =============================================================================
# RETRY HELPERS
# =============================================================================

def is_transient_error(error: Exception) -> bool:
    """Determine if an error is transient and should be retried."""
    # Our typed errors know if they're transient
    if isinstance(error, APIError):
        return error.is_transient

    # requests library errors
    if isinstance(error, requests.exceptions.Timeout):
        return True
    if isinstance(error, requests.exceptions.ConnectionError):
        return True

    # Check error message for common transient patterns
    message = str(error).lower()
    transient_patterns = [
        'timeout', 'timed out', 'connection refused', 'connection reset',
        'temporary failure', 'service unavailable', 'bad gateway',
        'gateway timeout', 'too many requests'
    ]
    return any(pattern in message for pattern in transient_patterns)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 1.0,
    should_retry: Optional[Callable[[Exception], bool]] = None
):
    """
    Decorator for retrying functions with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Maximum random jitter to add (prevents thundering herd)
        should_retry: Custom function to determine if error is retryable
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            retry_fn = should_retry or is_transient_error
            last_error: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Don't retry if max attempts reached or error is permanent
                    if attempt == max_attempts or not retry_fn(e):
                        raise

                    # Exponential backoff with jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    actual_jitter = random.uniform(0, jitter)
                    total_delay = delay + actual_jitter

                    # Log retry attempt
                    api_logger.warning(
                        f"Retry attempt {attempt}/{max_attempts}",
                        error=str(e),
                        error_type=type(e).__name__,
                        delay_seconds=round(total_delay, 2),
                        attempt=attempt
                    )

                    time.sleep(total_delay)

            # Should never reach here, but just in case
            if last_error:
                raise last_error
            raise RuntimeError("Retry loop exited unexpectedly")

        return wrapper
    return decorator


def classify_http_error(response: requests.Response, source: str) -> APIError:
    """Convert HTTP response to appropriate typed error."""
    status = response.status_code

    if status == 429:
        retry_after = response.headers.get('Retry-After')
        return RateLimitError(
            f"Rate limit exceeded for {source}",
            source,
            int(retry_after) if retry_after and retry_after.isdigit() else None
        )
    elif status >= 500:
        return ServerError(f"{source} server error: {status}", source, status)
    elif status >= 400:
        return ClientError(f"{source} client error: {status}", source, status)

    # Shouldn't reach here for error responses
    return APIError(f"Unknown error from {source}: {status}", source)


class MemecoinDataFetcher:
    """Fetches memecoin data from Birdeye and GoPlus (security) APIs."""

    BIRDEYE_API = "https://public-api.birdeye.so/defi/token_overview"
    GOPLUS_EVM_API = "https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
    GOPLUS_SOLANA_API = "https://api.gopluslabs.io/api/v1/solana/token_security"
    DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"

    # Chain configuration: maps chain names to API-specific values
    # goplus_chain_id: EVM numeric chain ID for GoPlus, or 'solana' for Solana
    # dexscreener_chain_id: Chain identifier for DexScreener
    CHAIN_CONFIG = {
        'solana':   {'birdeye': 'solana',   'goplus_chain_id': 'solana',  'native': 'SOL', 'dexscreener': 'solana'},
        'base':     {'birdeye': 'base',     'goplus_chain_id': '8453',    'native': 'ETH', 'dexscreener': 'base'},
        'ethereum': {'birdeye': 'ethereum', 'goplus_chain_id': '1',       'native': 'ETH', 'dexscreener': 'ethereum'},
        'bsc':      {'birdeye': 'bsc',      'goplus_chain_id': '56',      'native': 'BNB', 'dexscreener': 'bsc'},
        'polygon':  {'birdeye': 'polygon',  'goplus_chain_id': '137',     'native': 'MATIC', 'dexscreener': 'polygon'},
        'arbitrum': {'birdeye': 'arbitrum', 'goplus_chain_id': '42161',   'native': 'ETH', 'dexscreener': 'arbitrum'},
    }

    def __init__(self, timeout: int = 10, retry_attempts: int = 2, max_backoff: float = 60.0):
        """Initialize data fetcher with timeout and retry settings.
        
        Args:
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for transient errors
            max_backoff: Maximum backoff delay in seconds (default 60s)
        """
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.max_backoff = max_backoff
        self._api_cache = TTLCache(ttl_seconds=60)  # Instance-level cache

    def _make_request(self, url: str, source: str, headers: Optional[Dict] = None,
                      params: Optional[Dict] = None) -> requests.Response:
        """
        Make an HTTP request with proper error classification.

        Raises typed errors instead of generic exceptions so callers
        know exactly what went wrong and whether to retry.
        """
        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"{source} request timed out", source, cause=e)
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"{source} connection failed: {e}", source, cause=e)
        except requests.exceptions.RequestException as e:
            raise APIError(f"{source} request failed: {e}", source, cause=e)

        # Classify HTTP errors
        if response.status_code >= 400:
            raise classify_http_error(response, source)

        return response

    def _parse_json(self, response: requests.Response, source: str) -> Dict[str, Any]:
        """Parse JSON response with proper error handling."""
        try:
            return response.json()
        except (ValueError, KeyError) as e:
            raise ParseError(f"{source} returned invalid JSON", source, cause=e)

    def fetch_birdeye_data(self, address: str, blockchain: str = 'solana') -> Optional[Dict[str, Any]]:
        """Fetch market data from Birdeye API (primary source for all chains).
        
        Uses caching to reduce API calls for the same token within 60 seconds.
        Falls back to DexScreener if Birdeye fails.
        """
        chain_config = self.CHAIN_CONFIG.get(blockchain.lower(), self.CHAIN_CONFIG['solana'])
        cache_key = f"birdeye:{blockchain}:{address}"
        
        # Check cache first
        cached = self._api_cache.get(cache_key)
        if cached:
            api_logger.debug("Cache hit for Birdeye", token=address[:8], blockchain=blockchain)
            return cached

        if not BIRDEYE_API_KEY:
            api_logger.warning("Birdeye API key not configured, trying DexScreener fallback", 
                             token=address[:8], blockchain=blockchain)
            return self._fetch_dexscreener_fallback(address, blockchain)

        headers = {
            "X-API-KEY": BIRDEYE_API_KEY,
            "x-chain": chain_config['birdeye']
        }
        params = {"address": address}

        for attempt in range(1, self.retry_attempts + 1):
            with log_api_call(api_logger, self.BIRDEYE_API, 'GET', token=address[:8], attempt=attempt) as ctx:
                try:
                    response = self._make_request(
                        self.BIRDEYE_API, 'Birdeye', headers=headers, params=params
                    )
                    ctx['status_code'] = response.status_code

                    result = self._parse_json(response, 'Birdeye')

                    if not result.get('success') or not result.get('data'):
                        ctx['success'] = True  # API worked, just no data
                        api_logger.debug("Birdeye returned no data", token=address[:8])
                        return None

                    data = result['data']
                    ctx['has_data'] = True

                    result_data = {
                        'price_usd': float(data.get('price', 0)),
                        'liquidity_usd': float(data.get('liquidity', 0)),
                        'main_pool_liquidity': float(data.get('liquidity', 0)),
                        'total_liquidity': float(data.get('liquidity', 0)),
                        'main_pool_dex': 'Birdeye',
                        'volume_24h': float(data.get('v24hUSD', 0)),
                        'market_cap': float(data.get('marketCap', 0)),
                        'fdv': float(data.get('fdv', 0)),
                        'price_change_5m': data.get('priceChange5mPercent'),
                        'price_change_1h': data.get('priceChange1hPercent'),
                        'price_change_24h': data.get('priceChange24hPercent'),
                        'buy_count_24h': data.get('buy24h'),
                        'sell_count_24h': data.get('sell24h'),
                        'holder_count': data.get('holder'),
                        'unique_wallets_24h': data.get('uniqueWallet24h'),
                        'total_supply': data.get('totalSupply'),
                        'circulating_supply': data.get('circulatingSupply'),
                        'token_symbol': data.get('symbol'),
                        'token_name': data.get('name'),
                        'logo_uri': data.get('logoURI'),
                        'raw_data': data
                    }
                    
                    # Cache successful result
                    self._api_cache.set(cache_key, result_data)
                    return result_data

                except RateLimitError as e:
                    api_logger.warning("Birdeye rate limited",
                        token=address[:8], retry_after=e.retry_after, attempt=attempt)
                    if attempt < self.retry_attempts:
                        time.sleep(min(e.retry_after, 10))  # Wait up to 10s for rate limit
                        continue
                    # Try fallback on rate limit
                    return self._fetch_dexscreener_fallback(address, blockchain)

                except (TimeoutError, NetworkError, ServerError) as e:
                    # Transient errors - retry with backoff (use max_backoff from instance)
                    if attempt < self.retry_attempts:
                        delay = min((2 ** (attempt - 1)) + random.uniform(0, 1), self.max_backoff)
                        api_logger.warning("Birdeye transient error, retrying",
                            token=address[:8], error_type=type(e).__name__,
                            error=str(e), attempt=attempt, delay=round(delay, 2))
                        time.sleep(delay)
                        continue
                    # Try fallback after all retries exhausted
                    api_logger.warning("Birdeye failed, trying DexScreener fallback",
                        token=address[:8], error_type=type(e).__name__)
                    return self._fetch_dexscreener_fallback(address, blockchain)

                except (ClientError, ParseError, NoDataError) as e:
                    # Permanent errors - don't retry, try fallback
                    api_logger.warning("Birdeye permanent error, trying DexScreener fallback",
                        token=address[:8], error_type=type(e).__name__, error=str(e))
                    return self._fetch_dexscreener_fallback(address, blockchain)

                except (KeyError, ValueError, TypeError) as e:
                    # Data parsing issues - don't retry, try fallback
                    api_logger.warning("Birdeye data parsing failed, trying DexScreener fallback",
                        token=address[:8], error=str(e), error_type=type(e).__name__)
                    return self._fetch_dexscreener_fallback(address, blockchain)

        return None

    def fetch_security_data(self, address: str, blockchain: str = 'solana') -> Optional[Dict[str, Any]]:
        """Fetch token security data from GoPlus Security API (works on all chains)."""
        chain_config = self.CHAIN_CONFIG.get(blockchain.lower(), self.CHAIN_CONFIG['solana'])
        goplus_chain_id = chain_config.get('goplus_chain_id', 'solana')

        # Build URL based on chain type
        if goplus_chain_id == 'solana':
            url = f"{self.GOPLUS_SOLANA_API}?contract_addresses={address}"
        else:
            url = f"{self.GOPLUS_EVM_API.format(chain_id=goplus_chain_id)}?contract_addresses={address}"

        for attempt in range(1, self.retry_attempts + 1):
            with log_api_call(api_logger, url, 'GET', token=address[:8], attempt=attempt) as ctx:
                try:
                    response = self._make_request(url, 'GoPlus')
                    ctx['status_code'] = response.status_code

                    raw = self._parse_json(response, 'GoPlus')

                    if not raw.get('result'):
                        api_logger.debug("GoPlus returned no result", token=address[:8])
                        return None

                    # GoPlus keys results by lowercase address
                    token_key = address.lower() if goplus_chain_id != 'solana' else address
                    data = raw['result'].get(token_key)
                    if not data:
                        # Try any key in the result
                        data = next(iter(raw['result'].values()), None)
                    if not data:
                        api_logger.debug("GoPlus returned empty token data", token=address[:8])
                        return None

                    ctx['has_data'] = True

                    # Parse security fields — works for both EVM and Solana
                    if goplus_chain_id == 'solana':
                        # Solana-specific GoPlus format
                        mintable = data.get('mintable', {})
                        freezable = data.get('freezable', {})
                        mint_revoked = str(mintable.get('status', '0')) == '0'
                        freeze_revoked = str(freezable.get('status', '0')) == '0'
                        is_honeypot = False  # Not directly flagged on Solana
                        buy_tax = 0.0
                        sell_tax = 0.0
                        holder_count = 0  # Not in Solana response

                        # Top holders from Solana response
                        top_holders_raw = data.get('holders', [])
                        top_holders = [
                            {'address': h.get('account', ''), 'pct': float(h.get('percent', 0)) * 100}
                            for h in top_holders_raw
                        ]
                    else:
                        # EVM GoPlus format
                        mint_revoked = str(data.get('is_mintable', '0')) == '0'
                        freeze_revoked = not (
                            str(data.get('is_blacklisted', '0')) == '1'
                            or str(data.get('transfer_pausable', '0')) == '1'
                        )
                        is_honeypot = str(data.get('is_honeypot', '0')) == '1'
                        buy_tax = float(data.get('buy_tax', 0)) * 100  # GoPlus returns as decimal
                        sell_tax = float(data.get('sell_tax', 0)) * 100
                        holder_count = int(data.get('holder_count', 0))

                        # Top holders from EVM response
                        top_holders_raw = data.get('holders', [])
                        top_holders = [
                            {'address': h.get('address', ''), 'pct': float(h.get('percent', 0)) * 100}
                            for h in top_holders_raw
                        ]

                    # Calculate top holder percentages
                    top_holder_percent = top_holders[0]['pct'] if top_holders else 0.0
                    top_10_percent = sum(h['pct'] for h in top_holders[:10])

                    # Build a security score (0 = safest, higher = riskier)
                    # Mirrors what rugcheck_score did
                    security_score = 0.0
                    if not mint_revoked:
                        security_score += 3000
                    if not freeze_revoked:
                        security_score += 3000
                    if is_honeypot:
                        security_score += 5000
                    if top_holder_percent > 20:
                        security_score += 1000
                    if buy_tax > 5 or sell_tax > 5:
                        security_score += 1000

                    return {
                        'mint_authority_revoked': mint_revoked,
                        'freeze_authority_revoked': freeze_revoked,
                        'top_holder_percent': top_holder_percent,
                        'top_10_holders_percent': top_10_percent,
                        'holder_count': holder_count,
                        'rugcheck_score': security_score,  # Backward-compatible field name
                        'is_honeypot': is_honeypot,
                        'buy_tax': buy_tax,
                        'sell_tax': sell_tax,
                        'raw_data': data,
                        'top_holders': top_holders,
                    }

                except RateLimitError as e:
                    api_logger.warning("GoPlus rate limited",
                        token=address[:8], retry_after=e.retry_after, attempt=attempt)
                    if attempt < self.retry_attempts:
                        time.sleep(min(e.retry_after, 10))
                        continue
                    return None

                except (TimeoutError, NetworkError, ServerError) as e:
                    if attempt < self.retry_attempts:
                        delay = (2 ** (attempt - 1)) + random.uniform(0, 1)
                        api_logger.warning("GoPlus transient error, retrying",
                            token=address[:8], error_type=type(e).__name__,
                            error=str(e), attempt=attempt, delay=round(delay, 2))
                        time.sleep(delay)
                        continue
                    api_logger.error("GoPlus failed after all retries",
                        token=address[:8], error_type=type(e).__name__,
                        error=str(e), attempts=self.retry_attempts)
                    return None

                except (ClientError, ParseError, NoDataError) as e:
                    api_logger.error("GoPlus permanent error",
                        token=address[:8], error_type=type(e).__name__, error=str(e))
                    return None

                except (KeyError, ValueError, TypeError) as e:
                    api_logger.error("GoPlus data parsing failed",
                        token=address[:8], error=str(e), error_type=type(e).__name__)
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

        # Honeypot risk indicators
        honeypot_risk = data.get('honeypot_risk')
        if honeypot_risk == 'HIGH':
            red_flags.append("🔴 CRITICAL: HIGH honeypot risk - may not be sellable!")
        elif honeypot_risk == 'MEDIUM':
            red_flags.append("🟠 HIGH RISK: Moderate honeypot risk detected")

        # Token tax warnings
        buy_tax = data.get('estimated_buy_tax', 0)
        sell_tax = data.get('estimated_sell_tax', 0)
        if sell_tax > 20:
            red_flags.append(f"🔴 CRITICAL: Very high sell tax ({sell_tax:.0f}%)")
        elif sell_tax > 10:
            red_flags.append(f"🟠 HIGH RISK: High sell tax ({sell_tax:.0f}%)")
        elif sell_tax > 5:
            red_flags.append(f"🟡 MEDIUM: Moderate sell tax ({sell_tax:.0f}%)")

        if buy_tax > 10:
            red_flags.append(f"🟠 HIGH RISK: High buy tax ({buy_tax:.0f}%)")

        # Liquidity concentration warning
        top_10_holders = data.get('top_10_holders_percent', 0)
        if top_10_holders > 50:
            red_flags.append(f"🟠 HIGH RISK: Top 10 holders control {top_10_holders:.0f}%")

        # Buy/sell imbalance warning
        buy_sell_ratio = data.get('buy_sell_ratio')
        if buy_sell_ratio is not None and buy_sell_ratio < 0.3:
            red_flags.append(f"🟡 MEDIUM: Heavy selling pressure (buy/sell ratio: {buy_sell_ratio:.2f})")

        return red_flags

    def calculate_honeypot_risk(self, data: Dict[str, Any]) -> str:
        """
        Estimate honeypot risk based on available indicators.
        Returns: 'LOW', 'MEDIUM', or 'HIGH'
        """
        risk_score = 0

        # Check mint authority (can create infinite tokens)
        if not data.get('mint_authority_revoked', True):
            risk_score += 3

        # Check freeze authority (can freeze your tokens)
        if not data.get('freeze_authority_revoked', True):
            risk_score += 3

        # Very low liquidity makes selling difficult
        liquidity = data.get('liquidity_usd', 0)
        if liquidity < 5000:
            risk_score += 2
        elif liquidity < 10000:
            risk_score += 1

        # High sell tax indicator
        sell_tax = data.get('estimated_sell_tax', 0)
        if sell_tax > 20:
            risk_score += 3
        elif sell_tax > 10:
            risk_score += 2
        elif sell_tax > 5:
            risk_score += 1

        # Extreme holder concentration
        top_holder = data.get('top_holder_percent', 0)
        if top_holder > 50:
            risk_score += 2
        elif top_holder > 30:
            risk_score += 1

        # Very new token
        token_age = data.get('token_age_hours', 0)
        if token_age < 0.25:  # Less than 15 minutes
            risk_score += 1

        # Determine risk level
        if risk_score >= 5:
            return 'HIGH'
        elif risk_score >= 3:
            return 'MEDIUM'
        else:
            return 'LOW'

    def calculate_momentum_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate momentum indicators from price and volume data.
        Returns dict with momentum metrics.
        """
        momentum = {
            'buy_sell_ratio': None,
            'buy_sell_pressure': 'NEUTRAL',
            'volume_trend': 'UNKNOWN',
            'price_momentum': 'NEUTRAL',
            'momentum_score': 5.0  # Neutral score out of 10
        }

        # Buy/Sell Pressure Analysis
        buy_count = data.get('buy_count_24h')
        sell_count = data.get('sell_count_24h')

        if buy_count is not None and sell_count is not None and (buy_count + sell_count) > 0:
            total_txns = buy_count + sell_count
            momentum['buy_sell_ratio'] = buy_count / total_txns if total_txns > 0 else 0.5

            if momentum['buy_sell_ratio'] > 0.65:
                momentum['buy_sell_pressure'] = 'STRONG BUY'
            elif momentum['buy_sell_ratio'] > 0.55:
                momentum['buy_sell_pressure'] = 'BUY'
            elif momentum['buy_sell_ratio'] < 0.35:
                momentum['buy_sell_pressure'] = 'STRONG SELL'
            elif momentum['buy_sell_ratio'] < 0.45:
                momentum['buy_sell_pressure'] = 'SELL'
            else:
                momentum['buy_sell_pressure'] = 'NEUTRAL'

        # Price Momentum (based on price changes across timeframes)
        price_5m = data.get('price_change_5m') or 0
        price_1h = data.get('price_change_1h') or 0
        price_24h = data.get('price_change_24h') or 0

        # Weight recent changes more heavily
        weighted_change = (price_5m * 0.5) + (price_1h * 0.3) + (price_24h * 0.2)

        if weighted_change > 20:
            momentum['price_momentum'] = 'STRONG UP'
        elif weighted_change > 5:
            momentum['price_momentum'] = 'UP'
        elif weighted_change < -20:
            momentum['price_momentum'] = 'STRONG DOWN'
        elif weighted_change < -5:
            momentum['price_momentum'] = 'DOWN'
        else:
            momentum['price_momentum'] = 'NEUTRAL'

        # Volume Trend Analysis
        volume = data.get('volume_24h', 0)
        liquidity = data.get('liquidity_usd', 0)

        if liquidity > 0:
            vol_liq_ratio = volume / liquidity
            if vol_liq_ratio > 2.0:
                momentum['volume_trend'] = 'VERY HIGH'
            elif vol_liq_ratio > 1.0:
                momentum['volume_trend'] = 'HIGH'
            elif vol_liq_ratio > 0.3:
                momentum['volume_trend'] = 'NORMAL'
            elif vol_liq_ratio > 0.1:
                momentum['volume_trend'] = 'LOW'
            else:
                momentum['volume_trend'] = 'VERY LOW'

        # Calculate overall momentum score (0-10)
        score = 5.0  # Start neutral

        # Buy/sell pressure contribution (+/- 2 points)
        if momentum['buy_sell_pressure'] == 'STRONG BUY':
            score += 2.0
        elif momentum['buy_sell_pressure'] == 'BUY':
            score += 1.0
        elif momentum['buy_sell_pressure'] == 'STRONG SELL':
            score -= 2.0
        elif momentum['buy_sell_pressure'] == 'SELL':
            score -= 1.0

        # Price momentum contribution (+/- 2 points)
        if momentum['price_momentum'] == 'STRONG UP':
            score += 2.0
        elif momentum['price_momentum'] == 'UP':
            score += 1.0
        elif momentum['price_momentum'] == 'STRONG DOWN':
            score -= 2.0
        elif momentum['price_momentum'] == 'DOWN':
            score -= 1.0

        # Volume contribution (+/- 1 point)
        if momentum['volume_trend'] in ['VERY HIGH', 'HIGH']:
            score += 1.0
        elif momentum['volume_trend'] == 'VERY LOW':
            score -= 1.0

        momentum['momentum_score'] = max(0.0, min(10.0, score))

        return momentum

    # Note: Token tax estimation is handled by GoPlus Security API
    # which returns buy_tax and sell_tax fields.

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
            top_holders: List of top holder dicts from GoPlus (with 'address' and 'pct' keys)
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

        # Sort by tier (S > A > B > C) then by holding percent
        tier_order = {'S': 0, 'A': 1, 'B': 2, 'C': 3}
        matches.sort(key=lambda x: (tier_order.get(x['tier'], 4), -x['holding_percent']))

        return matches

    def analyze_holder_distribution(self, top_holders: List[Dict]) -> Dict[str, Any]:
        """
        Analyze holder distribution for concentration risk.

        Returns:
            Dict with distribution metrics
        """
        analysis = {
            'holder_concentration': 'UNKNOWN',
            'whale_count': 0,
            'top_holder_pct': 0,
            'top_5_pct': 0,
            'top_10_pct': 0,
            'distribution_score': 5.0  # Neutral score out of 10
        }

        if not top_holders:
            return analysis

        # Calculate metrics
        top_holder_pct = float(top_holders[0].get('pct', 0)) if top_holders else 0
        top_5_pct = sum(float(h.get('pct', 0)) for h in top_holders[:5])
        top_10_pct = sum(float(h.get('pct', 0)) for h in top_holders[:10])

        # Count whales (holders with > 3%)
        whale_count = sum(1 for h in top_holders if float(h.get('pct', 0)) > 3)

        analysis['top_holder_pct'] = top_holder_pct
        analysis['top_5_pct'] = top_5_pct
        analysis['top_10_pct'] = top_10_pct
        analysis['whale_count'] = whale_count

        # Determine concentration level
        if top_holder_pct > 30 or top_5_pct > 60:
            analysis['holder_concentration'] = 'CRITICAL'
            analysis['distribution_score'] = 1.0
        elif top_holder_pct > 20 or top_5_pct > 50:
            analysis['holder_concentration'] = 'HIGH'
            analysis['distribution_score'] = 3.0
        elif top_holder_pct > 10 or top_5_pct > 35:
            analysis['holder_concentration'] = 'MODERATE'
            analysis['distribution_score'] = 6.0
        elif top_holder_pct > 5:
            analysis['holder_concentration'] = 'LOW'
            analysis['distribution_score'] = 8.0
        else:
            analysis['holder_concentration'] = 'HEALTHY'
            analysis['distribution_score'] = 10.0

        return analysis

    # Native token addresses for fetching chain token prices
    NATIVE_TOKEN_ADDRESSES = {
        'SOL': 'So11111111111111111111111111111111111111112',
        'ETH': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH on Ethereum
        'BNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',  # WBNB on BSC
        'MATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',  # WMATIC on Polygon
    }

    def fetch_native_price(self, blockchain: str = 'solana') -> Optional[float]:
        """Fetch current native token price (SOL, ETH, BNB, etc.) from Birdeye."""
        chain_config = self.CHAIN_CONFIG.get(blockchain.lower(), {})
        native_token = chain_config.get('native', 'SOL')
        address = self.NATIVE_TOKEN_ADDRESSES.get(native_token)

        if not address:
            api_logger.warning("No native token address for chain", chain=blockchain)
            return None

        data = self.fetch_birdeye_data(address, blockchain=blockchain)
        if not data:
            return None
        return data.get('price_usd')

    def fetch_all_data(self, address: str, tracked_wallets: List[Dict[str, Any]] = None,
                       blockchain: str = 'solana') -> Optional[Dict[str, Any]]:
        """Fetch and combine data from all sources. Uses Birdeye as the only market data source."""
        blockchain = blockchain.lower()
        chain_config = self.CHAIN_CONFIG.get(blockchain, self.CHAIN_CONFIG['solana'])

        # Use Birdeye (only market data source)
        print(f"🔍 Fetching Birdeye data...")
        market_data = self.fetch_birdeye_data(address, blockchain=blockchain)
        data_source = "Birdeye"

        if not market_data:
            api_logger.error("All market data sources failed", token=address[:8],
                sources_tried=["Birdeye"])
            print("❌ Failed to fetch market data from any source")
            return None

        api_logger.info("Market data fetched successfully", token=address[:8], source=data_source)
        print(f"✅ Market data from {data_source}")

        # Get security data from GoPlus (all chains)
        print(f"🔍 Fetching security data...")
        security_data = self.fetch_security_data(address, blockchain=blockchain)

        # Combine all data
        combined_data = {
            'data_source': data_source,
            'liquidity_usd': market_data.get('liquidity_usd', 0),
            'main_pool_liquidity': market_data.get('main_pool_liquidity'),
            'total_liquidity': market_data.get('total_liquidity'),
            'main_pool_dex': market_data.get('main_pool_dex'),
            'volume_24h': market_data.get('volume_24h', 0),
            'price_usd': market_data.get('price_usd', 0),
            'market_cap': market_data.get('market_cap', 0),
            'price_change_5m': market_data.get('price_change_5m'),
            'price_change_1h': market_data.get('price_change_1h'),
            'price_change_24h': market_data.get('price_change_24h'),
            'buy_count_24h': market_data.get('buy_count_24h'),
            'sell_count_24h': market_data.get('sell_count_24h'),
            'token_symbol': market_data.get('token_symbol'),
            'token_name': market_data.get('token_name'),
            # ATH/ATL and liquidity locked data not available in basic APIs
            'all_time_high': None,
            'all_time_low': None,
            'price_vs_atl_percent': None,
            'liquidity_locked_percent': None,
        }

        # Token age not available from Birdeye
        combined_data['token_age_hours'] = 0.0

        # Security data (GoPlus)
        if security_data:
            combined_data.update({
                'holder_count': security_data.get('holder_count') or market_data.get('holder_count'),
                'top_holder_percent': security_data['top_holder_percent'],
                'top_10_holders_percent': security_data['top_10_holders_percent'],
                'mint_authority_revoked': 1 if security_data['mint_authority_revoked'] else 0,
                'freeze_authority_revoked': 1 if security_data['freeze_authority_revoked'] else 0,
                'rugcheck_score': security_data['rugcheck_score'],
            })

            # Token taxes directly from GoPlus
            combined_data.update({
                'estimated_buy_tax': security_data.get('buy_tax', 0.0),
                'estimated_sell_tax': security_data.get('sell_tax', 0.0),
                'tax_warning': 'POTENTIAL_HONEYPOT' if security_data.get('is_honeypot') else None,
            })

            # Analyze holder distribution using GoPlus top holders
            top_holders = security_data.get('top_holders', [])
            holder_analysis = self.analyze_holder_distribution(top_holders)
            combined_data.update(holder_analysis)
        else:
            # Set defaults if security check fails - use Birdeye holder count if available
            combined_data.update({
                'holder_count': market_data.get('holder_count'),
                'top_holder_percent': None,
                'top_10_holders_percent': None,
                'mint_authority_revoked': None,
                'freeze_authority_revoked': None,
                'rugcheck_score': None,
                'estimated_buy_tax': 0.0,
                'estimated_sell_tax': 0.0,
                'tax_warning': None,
            })

        # Check for smart money wallets
        smart_money_wallets = []
        smart_money_bonus = 0
        if tracked_wallets and security_data and security_data.get('top_holders'):
            top_holders = security_data['top_holders']
            smart_money_wallets = self.check_smart_money_wallets(top_holders, tracked_wallets)

            # Calculate smart money bonus for safety score
            wallet_count = len(smart_money_wallets)
            if wallet_count >= 3:
                smart_money_bonus = 2.0
            elif wallet_count >= 1:
                smart_money_bonus = 1.0

        combined_data['smart_money_wallets'] = smart_money_wallets
        combined_data['smart_money_count'] = len(smart_money_wallets)

        # Calculate honeypot risk
        combined_data['honeypot_risk'] = self.calculate_honeypot_risk(combined_data)

        # Calculate momentum indicators
        momentum = self.calculate_momentum_score(combined_data)
        combined_data.update(momentum)

        # Calculate safety score (base score)
        base_safety_score = self.calculate_safety_score(combined_data)

        # Adjust for honeypot risk
        honeypot_penalty = 0
        if combined_data['honeypot_risk'] == 'HIGH':
            honeypot_penalty = 3.0
        elif combined_data['honeypot_risk'] == 'MEDIUM':
            honeypot_penalty = 1.5

        # Add smart money bonus (capped at 10.0)
        combined_data['safety_score'] = max(0.0, min(10.0, base_safety_score + smart_money_bonus - honeypot_penalty))
        combined_data['smart_money_bonus'] = smart_money_bonus

        # Detect red flags (now includes honeypot and tax warnings)
        combined_data['red_flags'] = self.detect_red_flags(combined_data)

        # Store raw data
        combined_data['raw_data'] = {
            'birdeye': market_data.get('raw_data', {}),
            'goplus': security_data.get('raw_data', {}) if security_data else {}
        }

        # Fetch native token price for market context (SOL, ETH, BNB, etc.)
        native_price = self.fetch_native_price(blockchain=blockchain)
        if native_price:
            combined_data['sol_price_usd'] = native_price  # Keep column name for backward compatibility

        return combined_data


if __name__ == "__main__":
    # Test with BONK token
    print("Testing MemecoinDataFetcher with BONK token...")
    print("=" * 60)

    fetcher = MemecoinDataFetcher()
    address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

    data = fetcher.fetch_all_data(address)

    if data:
        print(f"\n✅ Data fetched successfully from {data.get('data_source', 'Unknown')}!")
        print("\n📊 MARKET DATA:")
        print(f"   Price: ${data.get('price_usd', 0):.8f}")
        print(f"   Liquidity: ${data.get('liquidity_usd', 0):,.2f}")
        print(f"   24h Volume: ${data.get('volume_24h', 0):,.2f}")
        print(f"   Market Cap: ${data.get('market_cap', 0):,.2f}")
        print(f"   Token Age: {data.get('token_age_hours', 0):.1f} hours")

        print("\n📈 PRICE CHANGES:")
        if data.get('price_change_5m') is not None:
            print(f"   5m: {data['price_change_5m']:+.2f}%")
        if data.get('price_change_1h') is not None:
            print(f"   1h: {data['price_change_1h']:+.2f}%")
        if data.get('price_change_24h') is not None:
            print(f"   24h: {data['price_change_24h']:+.2f}%")

        print("\n🔒 SECURITY DATA:")
        print(f"   Holders: {data.get('holder_count', 'N/A')}")
        print(f"   Top Holder: {data.get('top_holder_percent', 0):.2f}%")
        print(f"   Mint Revoked: {'✅' if data.get('mint_authority_revoked') else '❌'}")
        print(f"   Freeze Revoked: {'✅' if data.get('freeze_authority_revoked') else '❌'}")
        print(f"   Security Score: {data.get('rugcheck_score', 'N/A')}")

        # NEW: Honeypot risk
        print(f"\n🚨 HONEYPOT RISK: {data.get('honeypot_risk', 'UNKNOWN')}")

        # NEW: Token taxes
        buy_tax = data.get('estimated_buy_tax', 0)
        sell_tax = data.get('estimated_sell_tax', 0)
        if buy_tax > 0 or sell_tax > 0:
            print(f"💸 Token Taxes: Buy {buy_tax:.0f}% / Sell {sell_tax:.0f}%")

        # NEW: Holder distribution
        holder_conc = data.get('holder_concentration')
        if holder_conc:
            print(f"\n📊 HOLDER DISTRIBUTION:")
            print(f"   Concentration: {holder_conc}")
            print(f"   Top 5 Holders: {data.get('top_5_pct', 0):.1f}%")
            print(f"   Whale Count: {data.get('whale_count', 0)}")

        # NEW: Momentum indicators
        print(f"\n📈 MOMENTUM:")
        print(f"   Score: {data.get('momentum_score', 5):.1f}/10")
        print(f"   Buy/Sell Pressure: {data.get('buy_sell_pressure', 'NEUTRAL')}")
        print(f"   Price Momentum: {data.get('price_momentum', 'NEUTRAL')}")
        print(f"   Volume Trend: {data.get('volume_trend', 'UNKNOWN')}")

        print(f"\n🎯 SAFETY SCORE: {data.get('safety_score', 0):.1f}/10")

        if data.get('red_flags'):
            print("\n⚠️  RED FLAGS:")
            for flag in data['red_flags']:
                print(f"   {flag}")
        else:
            print("\n✅ No major red flags detected!")

    else:
        print("\n❌ Failed to fetch data")


    def _fetch_dexscreener_fallback(self, address: str, blockchain: str = 'solana') -> Optional[Dict[str, Any]]:
        """Fetch market data from DexScreener as fallback when Birdeye fails.
        
        Args:
            address: Token contract address
            blockchain: Blockchain identifier (solana, base, ethereum, etc.)
            
        Returns:
            Dict with market data or None if failed
        """
        chain_config = self.CHAIN_CONFIG.get(blockchain.lower(), self.CHAIN_CONFIG['solana'])
        
        # Check cache first
        cache_key = f"dexscreener:{blockchain}:{address}"
        cached = self._api_cache.get(cache_key)
        if cached:
            api_logger.debug("Cache hit for DexScreener", token=address[:8], blockchain=blockchain)
            return cached
        
        url = f"{self.DEXSCREENER_API}/{address}"
        
        try:
            with log_api_call(api_logger, url, 'GET', token=address[:8], source='DexScreener') as ctx:
                response = self._make_request(url, 'DexScreener')
                ctx['status_code'] = response.status_code
                
                result = self._parse_json(response, 'DexScreener')
                
                if not result.get('pairs'):
                    api_logger.debug("DexScreener returned no pairs", token=address[:8])
                    return None
                
                # Get the best pair (highest liquidity)
                pairs = result['pairs']
                best_pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                
                ctx['has_data'] = True
                
                # Extract data from DexScreener format
                price_usd = float(best_pair.get('priceUsd', 0))
                liquidity = float(best_pair.get('liquidity', {}).get('usd', 0) or 0)
                volume_24h = float(best_pair.get('volume', {}).get('h24', 0) or 0)
                market_cap = float(best_pair.get('fdv', 0) or 0)  # Fully diluted valuation
                
                # Price changes
                price_change_5m = best_pair.get('priceChange', {}).get('m5')
                price_change_1h = best_pair.get('priceChange', {}).get('h1')
                price_change_24h = best_pair.get('priceChange', {}).get('h24')
                
                # Buy/sell counts (may not be available)
                txns = best_pair.get('txns', {})
                buy_count_24h = txns.get('h24', {}).get('buys')
                sell_count_24h = txns.get('h24', {}).get('sells')
                
                result_data = {
                    'price_usd': price_usd,
                    'liquidity_usd': liquidity,
                    'main_pool_liquidity': liquidity,
                    'total_liquidity': liquidity,
                    'main_pool_dex': best_pair.get('dexId', 'DexScreener'),
                    'volume_24h': volume_24h,
                    'market_cap': market_cap,
                    'fdv': market_cap,
                    'price_change_5m': price_change_5m,
                    'price_change_1h': price_change_1h,
                    'price_change_24h': price_change_24h,
                    'buy_count_24h': buy_count_24h,
                    'sell_count_24h': sell_count_24h,
                    'holder_count': None,  # Not available from DexScreener
                    'unique_wallets_24h': None,
                    'total_supply': None,
                    'circulating_supply': None,
                    'token_symbol': best_pair.get('baseToken', {}).get('symbol'),
                    'token_name': best_pair.get('baseToken', {}).get('name'),
                    'logo_uri': best_pair.get('info', {}).get('imageUrl'),
                    'raw_data': best_pair,
                    'data_source': 'DexScreener'  # Mark as fallback source
                }
                
                # Cache the result
                self._api_cache.set(cache_key, result_data)
                api_logger.info("DexScreener fallback successful", 
                              token=address[:8], blockchain=blockchain)
                return result_data
                
        except Exception as e:
            api_logger.error("DexScreener fallback failed",
                           token=address[:8], error=str(e), error_type=type(e).__name__)
            return None


    def check_api_health(self) -> Dict[str, Any]:
        """Check health of all configured APIs.
        
        Returns:
            Dict with health status for each API
        """
        health = {
            'birdeye': {'healthy': False, 'latency_ms': None, 'error': None},
            'goplus': {'healthy': False, 'latency_ms': None, 'error': None},
            'dexscreener': {'healthy': False, 'latency_ms': None, 'error': None}
        }
        
        # Test Birdeye with a known token (BONK on Solana)
        if BIRDEYE_API_KEY:
            start = time.time()
            try:
                test_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
                result = self.fetch_birdeye_data(test_address, blockchain='solana')
                health['birdeye']['healthy'] = result is not None
                health['birdeye']['latency_ms'] = round((time.time() - start) * 1000, 2)
            except Exception as e:
                health['birdeye']['error'] = str(e)
        else:
            health['birdeye']['error'] = 'BIRDEYE_API_KEY not configured'
        
        # Test GoPlus with a known token
        start = time.time()
        try:
            test_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
            result = self.fetch_security_data(test_address, blockchain='solana')
            health['goplus']['healthy'] = result is not None
            health['goplus']['latency_ms'] = round((time.time() - start) * 1000, 2)
        except Exception as e:
            health['goplus']['error'] = str(e)
        
        # Test DexScreener
        start = time.time()
        try:
            test_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
            result = self._fetch_dexscreener_fallback(test_address, blockchain='solana')
            health['dexscreener']['healthy'] = result is not None
            health['dexscreener']['latency_ms'] = round((time.time() - start) * 1000, 2)
        except Exception as e:
            health['dexscreener']['error'] = str(e)
        
        return health
