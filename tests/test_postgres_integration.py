#!/usr/bin/env python3
"""
Integration tests for PostgreSQL/Supabase database operations.
These tests require a PostgreSQL database connection.
"""
import os
import unittest
from datetime import datetime, timedelta

# Skip all tests if no DATABASE_URL is set
SKIP_POSTGRES_TESTS = not os.environ.get('DATABASE_URL')

if not SKIP_POSTGRES_TESTS:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    import database as db_module
    from database import MemecoinDatabase


@unittest.skipIf(SKIP_POSTGRES_TESTS, "DATABASE_URL not set - skipping PostgreSQL tests")
class TestPostgreSQLIntegration(unittest.TestCase):
    """Integration tests for PostgreSQL database operations."""
    
    @classmethod
    def setUpClass(cls):
        """Set up database connection for all tests."""
        cls.db = MemecoinDatabase(use_pool=False)
        cls.assertEqual(cls.db.db_type, 'postgres', "Must use PostgreSQL for these tests")
    
    @classmethod
    def tearDownClass(cls):
        """Close database connection."""
        cls.db.close()
    
    def setUp(self):
        """Clean up test data before each test."""
        # Clean up any test data from previous runs
        self.db.cursor.execute("""
            DELETE FROM performance_history WHERE call_id IN (
                SELECT call_id FROM calls_received WHERE contract_address LIKE 'TEST_%'
            )
        """)
        self.db.cursor.execute("""
            DELETE FROM performance_tracking WHERE call_id IN (
                SELECT call_id FROM calls_received WHERE contract_address LIKE 'TEST_%'
            )
        """)
        self.db.cursor.execute("""
            DELETE FROM my_decisions WHERE call_id IN (
                SELECT call_id FROM calls_received WHERE contract_address LIKE 'TEST_%'
            )
        """)
        self.db.cursor.execute("""
            DELETE FROM initial_snapshot WHERE call_id IN (
                SELECT call_id FROM calls_received WHERE contract_address LIKE 'TEST_%'
            )
        """)
        self.db.cursor.execute("DELETE FROM calls_received WHERE contract_address LIKE 'TEST_%'")
        self.db.conn.commit()
    
    def test_boolean_handling_postgres(self):
        """Test that boolean values are correctly handled in PostgreSQL."""
        # Insert a call
        call_id = self.db.insert_call(
            contract_address="TEST_BOOL_001",
            token_symbol="TEST",
            token_name="Test Token",
            source="Test Source",
            blockchain="Solana"
        )
        self.assertGreater(call_id, 0)
        
        # Insert snapshot with boolean fields
        self.db.insert_snapshot(call_id, {
            'liquidity_usd': 100000.0,
            'mint_authority_revoked': True,
            'freeze_authority_revoked': False,
            'safety_score': 8.5,
            'raw_data': {'test': 'data'}
        })
        
        # Verify booleans were stored correctly
        self.db.cursor.execute(
            "SELECT mint_authority_revoked, freeze_authority_revoked FROM initial_snapshot WHERE call_id = %s",
            (call_id,)
        )
        row = self.db.cursor.fetchone()
        
        # PostgreSQL returns native booleans
        self.assertTrue(row['mint_authority_revoked'])
        self.assertFalse(row['freeze_authority_revoked'])
    
    def test_performance_history_insert(self):
        """Test inserting performance history rows."""
        call_id = self.db.insert_call(
            contract_address="TEST_HIST_001",
            token_symbol="HIST",
            token_name="History Test",
            source="Test",
            blockchain="Solana"
        )
        
        # Insert multiple history entries
        for i in range(5):
            self.db.insert_performance_history(call_id, {
                'decision_status': 'WATCH',
                'reference_price': 1.0,
                'price_usd': 1.0 + (i * 0.1),
                'liquidity_usd': 100000.0,
                'total_liquidity': 100000.0,
                'market_cap': 1000000.0,
                'gain_loss_pct': i * 10.0,
                'token_still_alive': 'yes',
                'rug_pull_occurred': None
            })
        
        # Verify all entries exist
        self.db.cursor.execute(
            "SELECT COUNT(*) as count FROM performance_history WHERE call_id = %s",
            (call_id,)
        )
        count = self.db.cursor.fetchone()['count']
        self.assertEqual(count, 5)
    
    def test_source_performance_update(self):
        """Test source performance statistics calculation."""
        source_name = "test_source_stats"
        
        # Create multiple calls for the same source
        for i in range(5):
            call_id = self.db.insert_call(
                contract_address=f"TEST_SRC_{i:03d}",
                token_symbol=f"SRC{i}",
                token_name=f"Source Token {i}",
                source=source_name,
                blockchain="Solana"
            )
            
            # Add decision (mix of TRADE and PASS)
            decision = "TRADE" if i < 3 else "PASS"
            self.db.insert_decision(
                call_id=call_id,
                decision=decision,
                trade_size_usd=100.0 if decision == "TRADE" else None,
                entry_price=1.0,
                reasoning_notes="test",
                emotional_state="calm",
                confidence_level=5
            )
            
            # Add performance data
            self.db.insert_or_update_performance(call_id, {
                'max_gain_observed': 50.0 + (i * 10),
                'rug_pull_occurred': 'no'
            })
        
        # Update source performance
        self.db.update_source_performance(source_name)
        
        # Verify stats
        sources = self.db.get_all_sources()
        test_source = next((s for s in sources if s['source_name'] == source_name), None)
        
        self.assertIsNotNone(test_source)
        self.assertEqual(test_source['total_calls'], 5)
        self.assertEqual(test_source['calls_traded'], 3)
    
    def test_concurrent_connection_handling(self):
        """Test that multiple database connections work correctly."""
        # Create multiple database instances
        dbs = [MemecoinDatabase(use_pool=False) for _ in range(3)]
        
        try:
            # Each should be able to perform operations
            for i, db in enumerate(dbs):
                call_id = db.insert_call(
                    contract_address=f"TEST_CONCURRENT_{i:03d}",
                    token_symbol=f"CON{i}",
                    token_name=f"Concurrent {i}",
                    source="Concurrent Test",
                    blockchain="Solana"
                )
                self.assertGreater(call_id, 0)
        finally:
            for db in dbs:
                db.close()
    
    def test_datetime_timezone_handling(self):
        """Test that datetime values are handled correctly."""
        call_id = self.db.insert_call(
            contract_address="TEST_TIME_001",
            token_symbol="TIME",
            token_name="Time Test",
            source="Test",
            blockchain="Solana"
        )
        
        # Insert with explicit timestamp
        test_time = datetime.now()
        self.db.cursor.execute("""
            INSERT INTO performance_history 
            (call_id, timestamp, decision_status, reference_price, price_usd, token_still_alive)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (call_id, test_time, 'WATCH', 1.0, 1.1, 'yes'))
        self.db.conn.commit()
        
        # Retrieve and verify
        self.db.cursor.execute(
            "SELECT timestamp FROM performance_history WHERE call_id = %s",
            (call_id,)
        )
        row = self.db.cursor.fetchone()
        
        # Should be a datetime object
        self.assertIsInstance(row['timestamp'], datetime)


@unittest.skipIf(not SKIP_POSTGRES_TESTS, "PostgreSQL tests enabled - skipping SQLite comparison")
class TestSQLiteBehavior(unittest.TestCase):
    """Test SQLite-specific behavior for comparison."""
    
    def setUp(self):
        """Set up SQLite database."""
        import tempfile
        import database as db_module
        
        # Ensure we're using SQLite
        self._orig_db_url = db_module.DATABASE_URL
        db_module.DATABASE_URL = None
        
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db = MemecoinDatabase(db_path=self.temp_file.name)
    
    def tearDown(self):
        """Clean up."""
        import database as db_module
        import os
        
        self.db.close()
        os.unlink(self.temp_file.name)
        db_module.DATABASE_URL = self._orig_db_url
    
    def test_sqlite_boolean_text_storage(self):
        """Test that SQLite stores booleans as text."""
        call_id = self.db.insert_call(
            contract_address="TEST_SQLITE_BOOL",
            token_symbol="BOOL",
            token_name="Bool Test",
            source="Test",
            blockchain="Solana"
        )
        
        self.db.insert_snapshot(call_id, {
            'liquidity_usd': 100000.0,
            'mint_authority_revoked': True,
            'freeze_authority_revoked': False,
            'safety_score': 8.5,
            'raw_data': {}
        })
        
        # In SQLite, booleans are stored as 'yes'/'no' text
        self.db.cursor.execute(
            "SELECT mint_authority_revoked, freeze_authority_revoked FROM initial_snapshot WHERE call_id = ?",
            (call_id,)
        )
        row = self.db.cursor.fetchone()
        
        self.assertEqual(row['mint_authority_revoked'], 'yes')
        self.assertEqual(row['freeze_authority_revoked'], 'no')


if __name__ == "__main__":
    # Print test configuration
    if SKIP_POSTGRES_TESTS:
        print("⚠️  DATABASE_URL not set - PostgreSQL integration tests will be skipped")
        print("   Set DATABASE_URL environment variable to run PostgreSQL tests")
    else:
        print(f"✅ Running PostgreSQL integration tests with: {os.environ.get('DATABASE_URL', '')[:50]}...")
    
    unittest.main()