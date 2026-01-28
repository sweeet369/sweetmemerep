#!/usr/bin/env python3
"""
Unit tests for GoPlus Security API integration.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_fetcher import MemecoinDataFetcher, APIError, RateLimitError, TimeoutError


class TestGoPlusSecurityAPI(unittest.TestCase):
    """Test cases for GoPlus Security API."""

    def setUp(self):
        """Set up test fixtures."""
        self.fetcher = MemecoinDataFetcher()
        
        # Sample Solana token address
        self.solana_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        
        # Sample EVM token address
        self.evm_address = "0xA0b86a33E6441E6C7D3D4B4f47E5F7e8c9D0E1F2"

    def test_chain_config_all_chains(self):
        """Test that all chains have required configuration."""
        required_keys = ['birdeye', 'goplus_chain_id', 'native', 'dexscreener']
        
        for chain_name, config in self.fetcher.CHAIN_CONFIG.items():
            for key in required_keys:
                self.assertIn(key, config, f"{chain_name} missing {key}")
                self.assertIsNotNone(config[key], f"{chain_name} has None for {key}")

    def test_goplus_url_building_solana(self):
        """Test URL building for Solana chain."""
        url = f"{self.fetcher.GOPLUS_SOLANA_API}?contract_addresses={self.solana_address}"
        expected = f"https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={self.solana_address}"
        self.assertEqual(url, expected)

    def test_goplus_url_building_evm(self):
        """Test URL building for EVM chains."""
        chain_id = "8453"  # Base
        url = f"{self.fetcher.GOPLUS_EVM_API.format(chain_id=chain_id)}?contract_addresses={self.evm_address}"
        expected = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={self.evm_address}"
        self.assertEqual(url, expected)

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_solana_success(self, mock_get):
        """Test successful Solana security data fetch."""
        # Mock response for Solana
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                self.solana_address: {
                    "mintable": {"status": "0"},
                    "freezable": {"status": "0"},
                    "holders": [
                        {"account": "holder1", "percent": "5.5"},
                        {"account": "holder2", "percent": "3.2"}
                    ]
                }
            }
        }
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_security_data(self.solana_address, blockchain='solana')
        
        self.assertIsNotNone(result)
        self.assertTrue(result['mint_authority_revoked'])
        self.assertTrue(result['freeze_authority_revoked'])
        self.assertEqual(result['top_holder_percent'], 5.5)
        self.assertEqual(len(result['top_holders']), 2)

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_evm_success(self, mock_get):
        """Test successful EVM security data fetch."""
        # Mock response for EVM (Base)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                self.evm_address.lower(): {
                    "is_mintable": "0",
                    "is_blacklisted": "0",
                    "transfer_pausable": "0",
                    "is_honeypot": "0",
                    "buy_tax": "0.05",
                    "sell_tax": "0.05",
                    "holder_count": "1500",
                    "holders": [
                        {"address": "holder1", "percent": "10.5"},
                        {"address": "holder2", "percent": "8.3"}
                    ]
                }
            }
        }
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_security_data(self.evm_address, blockchain='base')
        
        self.assertIsNotNone(result)
        self.assertTrue(result['mint_authority_revoked'])
        self.assertTrue(result['freeze_authority_revoked'])
        self.assertFalse(result['is_honeypot'])
        self.assertEqual(result['buy_tax'], 5.0)  # Converted to percentage
        self.assertEqual(result['sell_tax'], 5.0)
        self.assertEqual(result['holder_count'], 1500)

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_rate_limit(self, mock_get):
        """Test rate limit handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '30'}
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_security_data(self.solana_address, blockchain='solana')
        self.assertIsNone(result)  # Should return None after retries

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_timeout(self, mock_get):
        """Test timeout handling."""
        from data_fetcher import requests as df_requests
        mock_get.side_effect = df_requests.exceptions.Timeout("Connection timed out")

        result = self.fetcher.fetch_security_data(self.solana_address, blockchain='solana')
        self.assertIsNone(result)

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_empty_result(self, mock_get):
        """Test handling of empty result."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {}}
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_security_data(self.solana_address, blockchain='solana')
        self.assertIsNone(result)

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_invalid_json(self, mock_get):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_security_data(self.solana_address, blockchain='solana')
        self.assertIsNone(result)

    def test_security_score_calculation(self):
        """Test security score calculation."""
        # Test high risk (honeypot + mintable)
        high_risk_data = {
            'mint_authority_revoked': False,
            'freeze_authority_revoked': True,
            'is_honeypot': True,
            'top_holder_percent': 25.0,
            'buy_tax': 10.0,
            'sell_tax': 15.0
        }
        score = self._calculate_test_security_score(high_risk_data)
        self.assertGreater(score, 5000)  # Should be very high risk

        # Test low risk
        low_risk_data = {
            'mint_authority_revoked': True,
            'freeze_authority_revoked': True,
            'is_honeypot': False,
            'top_holder_percent': 5.0,
            'buy_tax': 0.0,
            'sell_tax': 0.0
        }
        score = self._calculate_test_security_score(low_risk_data)
        self.assertEqual(score, 0.0)  # Should be no risk

    def _calculate_test_security_score(self, data):
        """Helper to calculate security score like GoPlus does."""
        security_score = 0.0
        if not data.get('mint_authority_revoked', True):
            security_score += 3000
        if not data.get('freeze_authority_revoked', True):
            security_score += 3000
        if data.get('is_honeypot', False):
            security_score += 5000
        if data.get('top_holder_percent', 0) > 20:
            security_score += 1000
        if data.get('buy_tax', 0) > 5 or data.get('sell_tax', 0) > 5:
            security_score += 1000
        return security_score

    @patch('data_fetcher.requests.get')
    def test_fetch_security_data_all_chains(self, mock_get):
        """Test that security data can be fetched for all supported chains."""
        mock_response = Mock()
        mock_response.status_code = 200
        
        for chain in self.fetcher.CHAIN_CONFIG.keys():
            with self.subTest(chain=chain):
                if chain == 'solana':
                    mock_response.json.return_value = {
                        "result": {
                            self.solana_address: {
                                "mintable": {"status": "0"},
                                "freezable": {"status": "0"},
                                "holders": []
                            }
                        }
                    }
                else:
                    mock_response.json.return_value = {
                        "result": {
                            self.evm_address.lower(): {
                                "is_mintable": "0",
                                "is_blacklisted": "0",
                                "transfer_pausable": "0",
                                "is_honeypot": "0",
                                "buy_tax": "0",
                                "sell_tax": "0",
                                "holder_count": "100",
                                "holders": []
                            }
                        }
                    }
                
                mock_get.return_value = mock_response
                
                address = self.solana_address if chain == 'solana' else self.evm_address
                result = self.fetcher.fetch_security_data(address, blockchain=chain)
                
                self.assertIsNotNone(result, f"Failed to fetch for {chain}")
                self.assertIn('mint_authority_revoked', result)
                self.assertIn('freeze_authority_revoked', result)


class TestGoPlusCaching(unittest.TestCase):
    """Test caching behavior for GoPlus API calls."""

    def setUp(self):
        self.fetcher = MemecoinDataFetcher()
        self.fetcher._api_cache.clear()  # Clear cache before each test

    @patch('data_fetcher.requests.get')
    def test_caching_reduces_api_calls(self, mock_get):
        """Test that caching reduces the number of API calls."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "test_address": {
                    "mintable": {"status": "0"},
                    "freezable": {"status": "0"},
                    "holders": []
                }
            }
        }
        mock_get.return_value = mock_response

        address = "test_address"
        
        # First call should hit the API
        result1 = self.fetcher.fetch_security_data(address, blockchain='solana')
        self.assertEqual(mock_get.call_count, 1)
        
        # Second call should use cache
        result2 = self.fetcher.fetch_security_data(address, blockchain='solana')
        self.assertEqual(mock_get.call_count, 1)  # Should not increase
        
        # Results should be identical
        self.assertEqual(result1, result2)


if __name__ == "__main__":
    unittest.main()