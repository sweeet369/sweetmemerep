#!/usr/bin/env python3
"""
Focused unit tests for core logic that should not depend on live APIs.
"""
import tempfile
import unittest
from datetime import datetime, timedelta

import database as db_module
from database import MemecoinDatabase
from performance_tracker import PerformanceTracker


class TestCoreLogic(unittest.TestCase):
    def setUp(self):
        self._orig_db_url = db_module.DATABASE_URL
        self._orig_pool = db_module._pg_connection_pool
        db_module.DATABASE_URL = None
        db_module._pg_connection_pool = None

    def tearDown(self):
        db_module.DATABASE_URL = self._orig_db_url
        db_module._pg_connection_pool = self._orig_pool

    def test_normalize_sources(self):
        normalized = MemecoinDatabase.normalize_sources("  Alpha Group #3, Twitter Alpha ,  Discord Degen ")
        self.assertEqual(normalized, "alpha group #3, twitter alpha, discord degen")

    def test_record_exit_uses_entry_timestamp(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = MemecoinDatabase(db_path=tmp.name)
            call_id = db.insert_call(
                contract_address="TestTokenHoldDuration",
                token_symbol="TEST",
                token_name="Test Token",
                source="Test Source",
                blockchain="Solana",
            )

            entry_timestamp = (datetime.now() - timedelta(hours=2)).isoformat()
            db.insert_decision(
                call_id=call_id,
                decision="TRADE",
                trade_size_usd=100.0,
                entry_price=0.01,
                reasoning_notes="test",
                emotional_state="calm",
                confidence_level=5,
                entry_timestamp=entry_timestamp,
            )

            self.assertTrue(db.record_exit(call_id, 0.02))

            db.cursor.execute(
                "SELECT hold_duration_hours FROM my_decisions WHERE call_id = ?",
                (call_id,),
            )
            row = db.cursor.fetchone()
            self.assertIsNotNone(row)
            # If entry_timestamp is used, duration should be close to 2 hours (allow slack).
            self.assertGreater(row["hold_duration_hours"], 1.5)
            db.close()

    def test_tracker_prefers_trade_entry_price(self):
        tracker = PerformanceTracker()

        captured = {}

        def fake_update_token_performance(call_id, contract_address, entry_price, snapshot_timestamp, decision_status, blockchain):
            captured["entry_price"] = entry_price

        def fake_get_all_tracked_tokens():
            return [{
                "call_id": 1,
                "contract_address": "TestTokenPrice",
                "token_symbol": "TEST",
                "token_name": "Test Token",
                "source": "alpha",
                "blockchain": "Solana",
                "snapshot_timestamp": datetime.now().isoformat(),
                "call_price": 0.01,
                "trade_entry_price": 0.02,
                "my_decision": "TRADE",
                "actual_exit_price": None,
            }]

        tracker.update_token_performance = fake_update_token_performance
        tracker.get_all_tracked_tokens = fake_get_all_tracked_tokens
        tracker.db.update_source_performance = lambda _source: None

        tracker.run_update(limit=1)
        tracker.close()

        self.assertEqual(captured.get("entry_price"), 0.02)

    def test_update_source_performance_aggregates(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = MemecoinDatabase(db_path=tmp.name)

            call_id_1 = db.insert_call(
                contract_address="TestTokenSource1",
                token_symbol="T1",
                token_name="Token1",
                source="Alpha Calls",
                blockchain="Solana",
            )
            call_id_2 = db.insert_call(
                contract_address="TestTokenSource2",
                token_symbol="T2",
                token_name="Token2",
                source="Alpha Calls",
                blockchain="Solana",
            )

            db.insert_decision(
                call_id=call_id_1,
                decision="TRADE",
                trade_size_usd=100.0,
                entry_price=0.01,
                reasoning_notes="test",
                emotional_state="calm",
                confidence_level=5,
            )
            db.insert_decision(
                call_id=call_id_2,
                decision="PASS",
                trade_size_usd=None,
                entry_price=None,
                reasoning_notes="test",
                emotional_state="calm",
                confidence_level=5,
            )

            db.insert_or_update_performance(call_id_1, {"max_gain_observed": 60.0, "rug_pull_occurred": "no"})
            db.insert_or_update_performance(call_id_2, {"max_gain_observed": 10.0, "rug_pull_occurred": "no"})

            db.update_source_performance("Alpha Calls")
            sources = db.get_all_sources()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["total_calls"], 2)
            self.assertAlmostEqual(sources[0]["avg_max_gain"], 35.0, delta=0.1)
            db.close()

    def test_watch_to_trade_exit_flow(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = MemecoinDatabase(db_path=tmp.name)
            call_id = db.insert_call(
                contract_address="TestTokenWatch",
                token_symbol="TW",
                token_name="TokenWatch",
                source="Test Source",
                blockchain="Solana",
            )
            db.insert_decision(
                call_id=call_id,
                decision="WATCH",
                trade_size_usd=None,
                entry_price=0.01,
                reasoning_notes="watch",
                emotional_state="calm",
                confidence_level=5,
            )

            entry_ts = (datetime.now() - timedelta(hours=1)).isoformat()
            db.cursor.execute(
                """
                UPDATE my_decisions
                SET my_decision = 'TRADE',
                    trade_size_usd = ?,
                    entry_price = ?,
                    entry_timestamp = ?
                WHERE call_id = ? AND my_decision = 'WATCH'
                """,
                (100.0, 0.02, entry_ts, call_id),
            )
            db.conn.commit()

            self.assertTrue(db.record_exit(call_id, 0.03))
            db.cursor.execute(
                "SELECT actual_exit_price, hold_duration_hours FROM my_decisions WHERE call_id = ?",
                (call_id,),
            )
            row = db.cursor.fetchone()
            self.assertEqual(row["actual_exit_price"], 0.03)
            self.assertGreater(row["hold_duration_hours"], 0.5)
            db.close()

    def test_tracker_checkpoint_updates(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = MemecoinDatabase(db_path=tmp.name)
            call_id = db.insert_call(
                contract_address="TestTokenCheckpoint",
                token_symbol="TC",
                token_name="TokenCheckpoint",
                source="Test Source",
                blockchain="Solana",
            )
            db.insert_decision(
                call_id=call_id,
                decision="WATCH",
                trade_size_usd=None,
                entry_price=1.0,
                reasoning_notes="watch",
                emotional_state="calm",
                confidence_level=5,
            )

            tracker = PerformanceTracker()
            tracker.db.close()
            tracker.db = db
            tracker.fetch_current_price = lambda _address: {
                "price": 1.5,
                "liquidity": 2000.0,
                "total_liquidity": 2000.0,
                "market_cap": 10000.0,
                "exists": True,
            }

            snapshot_ts = (datetime.now() - timedelta(hours=2)).isoformat()
            tracker.update_token_performance(
                call_id=call_id,
                contract_address="TestTokenCheckpoint",
                entry_price=1.0,
                snapshot_timestamp=snapshot_ts,
                decision_status="WATCH",
                blockchain="solana",
            )

            db.cursor.execute(
                "SELECT checkpoint_type, price_15m_later, price_30m_later, price_1h_later, max_gain_observed FROM performance_tracking WHERE call_id = ?",
                (call_id,),
            )
            row = db.cursor.fetchone()
            self.assertEqual(row["checkpoint_type"], "1h")
            self.assertEqual(row["price_15m_later"], 1.5)
            self.assertEqual(row["price_30m_later"], 1.5)
            self.assertEqual(row["price_1h_later"], 1.5)
            self.assertAlmostEqual(row["max_gain_observed"], 50.0, delta=0.1)

            db.cursor.execute(
                "SELECT decision_status, price_usd, gain_loss_pct FROM performance_history WHERE call_id = ? ORDER BY timestamp DESC LIMIT 1",
                (call_id,),
            )
            hrow = db.cursor.fetchone()
            self.assertEqual(hrow["decision_status"], "WATCH")
            self.assertEqual(hrow["price_usd"], 1.5)
            self.assertAlmostEqual(hrow["gain_loss_pct"], 50.0, delta=0.1)
            tracker.close()

    def test_tracker_rug_detection_by_liquidity(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = MemecoinDatabase(db_path=tmp.name)
            call_id = db.insert_call(
                contract_address="TestTokenRug",
                token_symbol="TR",
                token_name="TokenRug",
                source="Test Source",
                blockchain="Solana",
            )
            db.insert_decision(
                call_id=call_id,
                decision="WATCH",
                trade_size_usd=None,
                entry_price=1.0,
                reasoning_notes="watch",
                emotional_state="calm",
                confidence_level=5,
            )

            tracker = PerformanceTracker()
            tracker.db.close()
            tracker.db = db
            tracker.fetch_current_price = lambda _address: {
                "price": 0.5,
                "liquidity": 500.0,
                "total_liquidity": 500.0,
                "market_cap": 1000.0,
                "exists": True,
            }

            snapshot_ts = (datetime.now() - timedelta(minutes=45)).isoformat()
            tracker.update_token_performance(
                call_id=call_id,
                contract_address="TestTokenRug",
                entry_price=1.0,
                snapshot_timestamp=snapshot_ts,
                decision_status="WATCH",
                blockchain="solana",
            )

            db.cursor.execute(
                "SELECT rug_pull_occurred, time_to_rug_hours FROM performance_tracking WHERE call_id = ?",
                (call_id,),
            )
            row = db.cursor.fetchone()
            self.assertEqual(row["rug_pull_occurred"], "yes")
            self.assertIsNotNone(row["time_to_rug_hours"])
            tracker.close()


if __name__ == "__main__":
    unittest.main()
