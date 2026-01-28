#!/usr/bin/env python3
"""
Tests for error handling paths and edge cases.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_fetcher import (
    MemecoinDataFetcher, APIError, RateLimitError, TimeoutError,
    NetworkError, ServerError, ClientError, ParseError, NoDataError
)
from performance_tracker import PerformanceTracker
import database as db_module
from database import MemecoinDatabase


class TestAPIErrorHandling(unittest.TestCase):
    """Test API error handling paths."""

    def setUp(self):
        self.fetcher = MemecoinDataFetcher()

    def test_transient_error_detection(self):
        """Test detection of transient vs permanent errors."""
        from data_fetcher import is_transient_error
        
        # Transient errors
        self.assertTrue(is_transient_error(TimeoutError("timeout", "test")))
        self.assertTrue(is_transient_error(NetworkError("connection refused", "test")))
        self.assertTrue(is_transient_error(ServerError("500", "test", 500)))
        self.assertTrue(is_transient_error(RateLimitError("429", "test")))
        
        # Permanent errors
        self.assertFalse(is_transient_error(ClientError("404", "test", 404)))
        self.assertFalse(is_transient_error(ParseError("bad json", "test")))
        self.assertFalse(is_transient_error(NoDataError("no data", "test")))
        
        # String-based detection
        self.assertTrue(is_transient_error(Exception("Connection timeout")))
        self.assertTrue(is_transient_error(Exception("Service unavailable")))

    @patch('data_fetcher.requests.get')
    def test_birdeye_all_retries_fail(self, mock_get):
        """Test when Birdeye fails after all retries."""
        mock_get.side_effect = TimeoutError("Connection timeout")
        
        result = self.fetcher.fetch_birdeye_data("test_address", blockchain='solana')
        
        # Should return None and try fallback
        self.assertIsNone(result)
        # Should have attempted retries
        self.assertGreater(mock_get.call_count, 0)

    @patch('data_fetcher.requests.get')
    def test_birdeye_fallback_to_dexscreener(self, mock_get):
        """Test fallback to DexScreener when Birdeye fails."""
        # First calls fail (Birdeye)
        mock_get.side_effect = [
            TimeoutError("Birdeye timeout"),  # First attempt
            TimeoutError("Birdeye timeout"),  # Retry
            Mock(  # DexScreener succeeds
                status_code=200,
                json=Mock(return_value={
                    "pairs": [{
                        "priceUsd": "1.5",
                        "liquidity": {"usd": "100000"},
                        "volume": {"h24": "50000"},
                        "fdv": "1000000",
                        "dexId": "raydium",
                        "baseToken": {"symbol": "TEST", "name": "Test Token"}
                    }]
                })
            )
        ]
        
        result = self.fetcher.fetch_birdeye_data("test_address", blockchain='solana')
        
        # Should get DexScreener data
        self.assertIsNotNone(result)
        self.assertEqual(result['data_source'], 'DexScreener')

    def test_invalid_blockchain_handling(self):
        """Test handling of invalid blockchain parameter."""
        # Should default to solana for unknown chains
        result = self.fetcher.fetch_birdeye_data("test_address", blockchain='invalid_chain')
        # Will fail without API key, but shouldn't crash

    def test_empty_address_handling(self):
        """Test handling of empty address."""
        result = self.fetcher.fetch_birdeye_data("", blockchain='solana')
        self.assertIsNone(result)


class TestDatabaseErrorHandling(unittest.TestCase):
    """Test database error handling paths."""

    def setUp(self):
        """Set up SQLite database for testing."""
        self._orig_db_url = db_module.DATABASE_URL
        db_module.DATABASE_URL = None
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db = MemecoinDatabase(db_path=self.temp_file.name)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        os.unlink(self.temp_file.name)
        db_module.DATABASE_URL = self._orig_db_url

    def test_duplicate_contract_insertion(self):
        """Test handling of duplicate contract addresses."""
        address = "DUPLICATE_TEST_001"
        
        # First insert should succeed
        call_id1 = self.db.insert_call(
            contract_address=address,
            token_symbol="DUP",
            token_name="Duplicate",
            source="Test",
            blockchain="Solana"
        )
        self.assertGreater(call_id1, 0)
        
        # Second insert should return existing call_id
        call_id2 = self.db.insert_call(
            contract_address=address,
            token_symbol="DUP2",
            token_name="Duplicate2",
            source="Test2",
            blockchain="Solana"
        )
        self.assertEqual(call_id1, call_id2)

    def test_invalid_call_id_handling(self):
        """Test handling of invalid call_id references."""
        # Try to insert snapshot for non-existent call
        result = self.db.insert_snapshot(99999, {
            'liquidity_usd': 100000,
            'safety_score': 8.0
        })
        # Should handle gracefully (foreign key constraint)

    def test_null_value_handling(self):
        """Test handling of NULL values in database."""
        call_id = self.db.insert_call(
            contract_address="NULL_TEST_001",
            token_symbol="NULL",
            token_name="Null Test",
            source="Test",
            blockchain="Solana"
        )
        
        # Insert with NULL values
        self.db.insert_decision(
            call_id=call_id,
            decision="PASS",
            trade_size_usd=None,
            entry_price=None,
            reasoning_notes="",
            emotional_state="neutral",
            confidence_level=None
        )
        
        # Should handle NULLs gracefully
        self.db.cursor.execute(
            "SELECT * FROM my_decisions WHERE call_id = ?",
            (call_id,)
        )
        row = self.db.cursor.fetchone()
        self.assertIsNotNone(row)


class TestPerformanceTrackerErrorHandling(unittest.TestCase):
    """Test performance tracker error handling."""

    def setUp(self):
        """Set up tracker with mocked dependencies."""
        self._orig_db_url = db_module.DATABASE_URL
        db_module.DATABASE_URL = None
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        
        self.tracker = PerformanceTracker(use_parallel=False)
        self.tracker.db.close()
        self.tracker.db = MemecoinDatabase(db_path=self.temp_file.name)

    def tearDown(self):
        """Clean up."""
        self.tracker.close()
        os.unlink(self.temp_file.name)
        db_module.DATABASE_URL = self._orig_db_url
        # Clean up dead letter file
        if os.path.exists(self.tracker.DEAD_LETTER_FILE):
            os.remove(self.tracker.DEAD_LETTER_FILE)

    def test_dead_letter_queue_creation(self):
        """Test that failed updates are added to dead letter queue."""
        # Create a token that will fail
        token = {
            'call_id': 99999,  # Invalid call_id
            'token_symbol': 'FAIL',
            'contract_address': 'INVALID_ADDRESS',
            'source': 'Test',
            'blockchain': 'solana',
            'snapshot_timestamp': '2024-01-01T00:00:00',
            'call_price': 1.0,
            'trade_entry_price': None,
            'my_decision': 'WATCH'
        }
        
        # Force an error
        self.tracker.fetcher.fetch_birdeye_data = Mock(side_effect=Exception("API Error"))
        
        # Update should fail but not crash
        result = self.tracker._update_single_token(token)
        
        self.assertFalse(result['success'])
        self.assertIsNotNone(result['error'])
        
        # Check dead letter queue
        dead_letters = self.tracker.get_dead_letter_queue()
        self.assertGreater(len(dead_letters), 0)
        
        # Verify entry structure
        entry = dead_letters[-1]
        self.assertIn('timestamp', entry)
        self.assertIn('token_symbol', entry)
        self.assertIn('error', entry)

    def test_dead_letter_queue_limit(self):
        """Test that dead letter queue is limited to 1000 entries."""
        # Add many entries
        for i in range(1100):
            self.tracker._add_to_dead_letter({
                'call_id': i,
                'token_symbol': f'TOKEN{i}',
                'contract_address': f'ADDR{i}',
                'blockchain': 'solana',
                'source': 'Test'
            }, f"Error {i}")
        
        # Should only keep last 1000
        dead_letters = self.tracker.get_dead_letter_queue()
        self.assertLessEqual(len(dead_letters), 1000)

    def test_empty_token_list_handling(self):
        """Test handling of empty token list."""
        # Mock get_all_tracked_tokens to return empty list
        self.tracker.get_all_tracked_tokens = Mock(return_value=[])
        
        # Should handle gracefully
        self.tracker.run_update()
        # Should print message about no tokens

    def test_api_health_check_failure(self):
        """Test behavior when API health check fails."""
        self.tracker.fetcher.check_api_health = Mock(return_value={
            'birdeye': {'healthy': False, 'error': 'API Key missing'},
            'goplus': {'healthy': True, 'latency_ms': 100},
            'dexscreener': {'healthy': True, 'latency_ms': 150}
        })
        
        health = self.tracker.check_api_health()
        self.assertFalse(all(h['healthy'] for h in health.values()))


class TestDataFetcherEdgeCases(unittest.TestCase):
    """Test edge cases in data fetcher."""

    def setUp(self):
        self.fetcher = MemecoinDataFetcher()

    def test_calculate_token_age_with_none(self):
        """Test token age calculation with None timestamp."""
        age = self.fetcher.calculate_token_age_hours(None)
        self.assertEqual(age, 0.0)

    def test_calculate_token_age_with_zero(self):
        """Test token age calculation with zero timestamp."""
        age = self.fetcher.calculate_token_age_hours(0)
        self.assertGreater(age, 0)  # Should be very old

    def test_calculate_gain_loss_edge_cases(self):
        """Test gain/loss calculation edge cases."""
        tracker = PerformanceTracker()
        
        # Both prices None
        self.assertIsNone(tracker.calculate_gain_loss(None, None))
        
        # Entry price None
        self.assertIsNone(tracker.calculate_gain_loss(None, 2.0))
        
        # Current price None
        self.assertIsNone(tracker.calculate_gain_loss(1.0, None))
        
        # Zero entry price
        self.assertIsNone(tracker.calculate_gain_loss(0, 2.0))
        
        # Normal case
        result = tracker.calculate_gain_loss(1.0, 2.0)
        self.assertEqual(result, 100.0)
        
        # Loss case
        result = tracker.calculate_gain_loss(2.0, 1.0)
        self.assertEqual(result, -50.0)
        
        tracker.close()

    def test_detect_red_flags_empty_data(self):
        """Test red flag detection with empty data."""
        flags = self.fetcher.detect_red_flags({})
        # Should still work with defaults
        self.assertIsInstance(flags, list)

    def test_detect_red_flags_critical_liquidity(self):
        """Test red flag detection for critical low liquidity."""
        flags = self.fetcher.detect_red_flags({
            'liquidity_usd': 1000,  # Way below 20K threshold
            'mint_authority_revoked': False,
            'freeze_authority_revoked': False,
            'top_holder_percent': 50,
            'token_age_hours': 0.1,
            'volume_24h': 0
        })
        
        # Should have multiple critical flags
        critical_flags = [f for f in flags if 'CRITICAL' in f]
        self.assertGreater(len(critical_flags), 0)

    def test_calculate_safety_score_bounds(self):
        """Test that safety score stays within 0-10 bounds."""
        # Perfect token
        perfect_score = self.fetcher.calculate_safety_score({
            'liquidity_usd': 200000,
            'mint_authority_revoked': True,
            'freeze_authority_revoked': True,
            'top_holder_percent': 1,
            'token_age_hours': 10,
            'volume_24h': 100000
        })
        self.assertGreaterEqual(perfect_score, 0)
        self.assertLessEqual(perfect_score, 10)
        
        # Terrible token
        terrible_score = self.fetcher.calculate_safety_score({
            'liquidity_usd': 1000,
            'mint_authority_revoked': False,
            'freeze_authority_revoked': False,
            'top_holder_percent': 80,
            'token_age_hours': 0.1,
            'volume_24h': 10
        })
        self.assertGreaterEqual(terrible_score, 0)
        self.assertLessEqual(terrible_score, 10)


class TestCachingBehavior(unittest.TestCase):
    """Test caching behavior."""

    def setUp(self):
        self.fetcher = MemecoinDataFetcher()
        self.fetcher._api_cache.clear()

    def test_cache_ttl_expiration(self):
        """Test that cache entries expire after TTL."""
        from data_fetcher import TTLCache
        import time
        
        # Create cache with very short TTL
        cache = TTLCache(ttl_seconds=0.1)
        
        # Add entry
        cache.set("test_key", {"data": "value"})
        
        # Should exist immediately
        self.assertIsNotNone(cache.get("test_key"))
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        self.assertIsNone(cache.get("test_key"))

    def test_cache_cleanup(self):
        """Test cache cleanup of expired entries."""
        from data_fetcher import TTLCache
        import time
        
        cache = TTLCache(ttl_seconds=0.1)
        
        # Add multiple entries
        for i in range(5):
            cache.set(f"key_{i}", {"data": i})
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Cleanup should remove all
        cleaned = cache.cleanup_expired()
        self.assertEqual(cleaned, 5)


if __name__ == "__main__":
    unittest.main()