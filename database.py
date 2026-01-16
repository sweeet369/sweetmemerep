import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List


class MemecoinDatabase:
    """SQLite database manager for memecoin trading analyzer."""

    def __init__(self, db_path: str = "memecoin_analyzer.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create all database tables if they don't exist."""

        # Table 1: calls_received
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS calls_received (
                call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_received TEXT NOT NULL,
                contract_address TEXT UNIQUE NOT NULL,
                token_symbol TEXT,
                token_name TEXT,
                source TEXT,
                blockchain TEXT DEFAULT 'Solana'
            )
        ''')

        # Table 2: initial_snapshot
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS initial_snapshot (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                snapshot_timestamp TEXT NOT NULL,
                liquidity_usd REAL,
                holder_count INTEGER,
                top_holder_percent REAL,
                top_10_holders_percent REAL,
                token_age_hours REAL,
                market_cap REAL,
                volume_24h REAL,
                price_usd REAL,
                mint_authority_revoked INTEGER,
                freeze_authority_revoked INTEGER,
                rugcheck_score REAL,
                safety_score REAL,
                raw_data TEXT,
                FOREIGN KEY (call_id) REFERENCES calls_received (call_id)
            )
        ''')

        # Table 3: my_decisions
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS my_decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                timestamp_decision TEXT NOT NULL,
                my_decision TEXT NOT NULL,
                trade_size_usd REAL,
                entry_price REAL,
                reasoning_notes TEXT,
                emotional_state TEXT,
                confidence_level INTEGER,
                FOREIGN KEY (call_id) REFERENCES calls_received (call_id)
            )
        ''')

        # Table 4: performance_tracking
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_tracking (
                tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                last_updated TEXT NOT NULL,
                price_1h_later REAL,
                price_24h_later REAL,
                price_7d_later REAL,
                price_30d_later REAL,
                current_mcap REAL,
                current_liquidity REAL,
                max_gain_observed REAL,
                max_loss_observed REAL,
                token_still_alive TEXT,
                rug_pull_occurred TEXT,
                FOREIGN KEY (call_id) REFERENCES calls_received (call_id)
            )
        ''')

        # Add columns if they don't exist (for existing databases)
        try:
            self.cursor.execute('ALTER TABLE performance_tracking ADD COLUMN current_mcap REAL')
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

        try:
            self.cursor.execute('ALTER TABLE performance_tracking ADD COLUMN current_liquidity REAL')
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

        # Migration: Add new columns to my_decisions
        migrations_my_decisions = [
            'ALTER TABLE my_decisions ADD COLUMN chart_assessment TEXT',
            'ALTER TABLE my_decisions ADD COLUMN actual_exit_price REAL',
            'ALTER TABLE my_decisions ADD COLUMN hold_duration_hours REAL'
        ]
        for migration in migrations_my_decisions:
            try:
                self.cursor.execute(migration)
                self.conn.commit()
            except sqlite3.OperationalError:
                pass

        # Migration: Add new columns to initial_snapshot
        migrations_initial_snapshot = [
            'ALTER TABLE initial_snapshot ADD COLUMN price_vs_atl_percent REAL',
            'ALTER TABLE initial_snapshot ADD COLUMN buy_count_24h INTEGER',
            'ALTER TABLE initial_snapshot ADD COLUMN sell_count_24h INTEGER',
            'ALTER TABLE initial_snapshot ADD COLUMN price_change_5m REAL',
            'ALTER TABLE initial_snapshot ADD COLUMN price_change_1h REAL',
            'ALTER TABLE initial_snapshot ADD COLUMN price_change_24h REAL',
            'ALTER TABLE initial_snapshot ADD COLUMN all_time_high REAL',
            'ALTER TABLE initial_snapshot ADD COLUMN all_time_low REAL',
            'ALTER TABLE initial_snapshot ADD COLUMN liquidity_locked_percent REAL'
        ]
        for migration in migrations_initial_snapshot:
            try:
                self.cursor.execute(migration)
                self.conn.commit()
            except sqlite3.OperationalError:
                pass

        # Migration: Add new columns to performance_tracking
        migrations_performance_tracking = [
            'ALTER TABLE performance_tracking ADD COLUMN checkpoint_type TEXT',
            'ALTER TABLE performance_tracking ADD COLUMN max_price_since_entry REAL',
            'ALTER TABLE performance_tracking ADD COLUMN min_price_since_entry REAL'
        ]
        for migration in migrations_performance_tracking:
            try:
                self.cursor.execute(migration)
                self.conn.commit()
            except sqlite3.OperationalError:
                pass

        # Table 5: source_performance
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_performance (
                source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT UNIQUE NOT NULL,
                total_calls INTEGER DEFAULT 0,
                calls_traded INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                avg_max_gain REAL DEFAULT 0.0,
                rug_rate REAL DEFAULT 0.0,
                tier TEXT DEFAULT 'C',
                last_updated TEXT NOT NULL
            )
        ''')

        # Table 6: tracked_wallets
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracked_wallets (
                wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT UNIQUE NOT NULL,
                wallet_name TEXT NOT NULL,
                total_tracked_buys INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                avg_gain REAL DEFAULT 0.0,
                tier TEXT DEFAULT 'C',
                notes TEXT,
                date_added TEXT NOT NULL
            )
        ''')

        self.conn.commit()

    def insert_call(self, contract_address: str, token_symbol: str, token_name: str,
                    source: str, blockchain: str = "Solana") -> int:
        """Insert a new call received record."""
        timestamp = datetime.now().isoformat()

        try:
            self.cursor.execute('''
                INSERT INTO calls_received
                (timestamp_received, contract_address, token_symbol, token_name, source, blockchain)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, contract_address, token_symbol, token_name, source, blockchain))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            # Contract address already exists, return existing call_id
            self.cursor.execute(
                'SELECT call_id FROM calls_received WHERE contract_address = ?',
                (contract_address,)
            )
            return self.cursor.fetchone()[0]

    def insert_snapshot(self, call_id: int, data: Dict[str, Any]) -> int:
        """Insert initial snapshot data."""
        timestamp = datetime.now().isoformat()

        self.cursor.execute('''
            INSERT INTO initial_snapshot (
                call_id, snapshot_timestamp, liquidity_usd, holder_count,
                top_holder_percent, top_10_holders_percent, token_age_hours,
                market_cap, volume_24h, price_usd, mint_authority_revoked,
                freeze_authority_revoked, rugcheck_score, safety_score, raw_data,
                price_vs_atl_percent, buy_count_24h, sell_count_24h,
                price_change_5m, price_change_1h, price_change_24h,
                all_time_high, all_time_low, liquidity_locked_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            call_id,
            timestamp,
            data.get('liquidity_usd'),
            data.get('holder_count'),
            data.get('top_holder_percent'),
            data.get('top_10_holders_percent'),
            data.get('token_age_hours'),
            data.get('market_cap'),
            data.get('volume_24h'),
            data.get('price_usd'),
            data.get('mint_authority_revoked'),
            data.get('freeze_authority_revoked'),
            data.get('rugcheck_score'),
            data.get('safety_score'),
            json.dumps(data.get('raw_data', {})),
            data.get('price_vs_atl_percent'),
            data.get('buy_count_24h'),
            data.get('sell_count_24h'),
            data.get('price_change_5m'),
            data.get('price_change_1h'),
            data.get('price_change_24h'),
            data.get('all_time_high'),
            data.get('all_time_low'),
            data.get('liquidity_locked_percent')
        ))
        self.conn.commit()
        return self.cursor.lastrowid

    def insert_decision(self, call_id: int, decision: str, trade_size_usd: Optional[float],
                       entry_price: Optional[float], reasoning_notes: str,
                       emotional_state: str, confidence_level: int,
                       chart_assessment: Optional[str] = None) -> int:
        """Insert user's trading decision."""
        timestamp = datetime.now().isoformat()

        self.cursor.execute('''
            INSERT INTO my_decisions (
                call_id, timestamp_decision, my_decision, trade_size_usd,
                entry_price, reasoning_notes, emotional_state, confidence_level,
                chart_assessment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (call_id, timestamp, decision, trade_size_usd, entry_price,
              reasoning_notes, emotional_state, confidence_level, chart_assessment))
        self.conn.commit()
        return self.cursor.lastrowid

    def record_exit(self, call_id: int, exit_price: float) -> bool:
        """Record exit from a trade and calculate hold duration."""
        # Get the decision entry timestamp
        self.cursor.execute('''
            SELECT timestamp_decision FROM my_decisions
            WHERE call_id = ? AND my_decision = 'TRADE'
        ''', (call_id,))

        result = self.cursor.fetchone()
        if not result:
            return False

        entry_time = datetime.fromisoformat(result['timestamp_decision'])
        exit_time = datetime.now()
        hold_duration = (exit_time - entry_time).total_seconds() / 3600  # hours

        # Update the decision record with exit data
        self.cursor.execute('''
            UPDATE my_decisions SET
                actual_exit_price = ?,
                hold_duration_hours = ?
            WHERE call_id = ? AND my_decision = 'TRADE'
        ''', (exit_price, hold_duration, call_id))

        self.conn.commit()
        return True

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades (TRADE decisions without exit recorded)."""
        self.cursor.execute('''
            SELECT
                c.call_id,
                c.token_symbol,
                c.token_name,
                c.contract_address,
                d.entry_price,
                d.trade_size_usd,
                d.timestamp_decision,
                d.chart_assessment,
                d.reasoning_notes
            FROM calls_received c
            JOIN my_decisions d ON c.call_id = d.call_id
            WHERE d.my_decision = 'TRADE' AND d.actual_exit_price IS NULL
            ORDER BY d.timestamp_decision DESC
        ''')
        return [dict(row) for row in self.cursor.fetchall()]

    def insert_or_update_performance(self, call_id: int, data: Dict[str, Any]) -> int:
        """Insert or update performance tracking data."""
        timestamp = datetime.now().isoformat()

        # Check if record exists
        self.cursor.execute(
            'SELECT tracking_id FROM performance_tracking WHERE call_id = ?',
            (call_id,)
        )
        existing = self.cursor.fetchone()

        if existing:
            # Update existing record
            self.cursor.execute('''
                UPDATE performance_tracking SET
                    last_updated = ?,
                    price_1h_later = COALESCE(?, price_1h_later),
                    price_24h_later = COALESCE(?, price_24h_later),
                    price_7d_later = COALESCE(?, price_7d_later),
                    price_30d_later = COALESCE(?, price_30d_later),
                    current_mcap = ?,
                    current_liquidity = ?,
                    max_gain_observed = COALESCE(?, max_gain_observed),
                    max_loss_observed = COALESCE(?, max_loss_observed),
                    token_still_alive = COALESCE(?, token_still_alive),
                    rug_pull_occurred = COALESCE(?, rug_pull_occurred),
                    checkpoint_type = COALESCE(?, checkpoint_type),
                    max_price_since_entry = COALESCE(?, max_price_since_entry),
                    min_price_since_entry = COALESCE(?, min_price_since_entry)
                WHERE call_id = ?
            ''', (
                timestamp,
                data.get('price_1h_later'),
                data.get('price_24h_later'),
                data.get('price_7d_later'),
                data.get('price_30d_later'),
                data.get('current_mcap'),
                data.get('current_liquidity'),
                data.get('max_gain_observed'),
                data.get('max_loss_observed'),
                data.get('token_still_alive'),
                data.get('rug_pull_occurred'),
                data.get('checkpoint_type'),
                data.get('max_price_since_entry'),
                data.get('min_price_since_entry'),
                call_id
            ))
            tracking_id = existing[0]
        else:
            # Insert new record
            self.cursor.execute('''
                INSERT INTO performance_tracking (
                    call_id, last_updated, price_1h_later, price_24h_later,
                    price_7d_later, price_30d_later, current_mcap, current_liquidity,
                    max_gain_observed, max_loss_observed, token_still_alive, rug_pull_occurred,
                    checkpoint_type, max_price_since_entry, min_price_since_entry
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                call_id, timestamp,
                data.get('price_1h_later'),
                data.get('price_24h_later'),
                data.get('price_7d_later'),
                data.get('price_30d_later'),
                data.get('current_mcap'),
                data.get('current_liquidity'),
                data.get('max_gain_observed'),
                data.get('max_loss_observed'),
                data.get('token_still_alive'),
                data.get('rug_pull_occurred'),
                data.get('checkpoint_type'),
                data.get('max_price_since_entry'),
                data.get('min_price_since_entry')
            ))
            tracking_id = self.cursor.lastrowid

        self.conn.commit()
        return tracking_id

    def update_source_performance(self, source_name: str):
        """Calculate and update source performance statistics."""
        timestamp = datetime.now().isoformat()

        # Get all calls from this source
        self.cursor.execute('''
            SELECT
                c.call_id,
                d.my_decision,
                p.max_gain_observed,
                p.rug_pull_occurred
            FROM calls_received c
            LEFT JOIN my_decisions d ON c.call_id = d.call_id
            LEFT JOIN performance_tracking p ON c.call_id = p.call_id
            WHERE c.source = ?
        ''', (source_name,))

        calls = self.cursor.fetchall()
        total_calls = len(calls)
        calls_traded = sum(1 for c in calls if c['my_decision'] == 'TRADE')

        gains = [c['max_gain_observed'] for c in calls if c['max_gain_observed'] is not None]
        avg_max_gain = sum(gains) / len(gains) if gains else 0.0

        rugs = sum(1 for c in calls if c['rug_pull_occurred'] == 'yes')
        rug_rate = rugs / total_calls if total_calls > 0 else 0.0

        wins = sum(1 for c in calls if c['max_gain_observed'] and c['max_gain_observed'] > 0)
        win_rate = wins / calls_traded if calls_traded > 0 else 0.0

        # Determine tier
        if avg_max_gain > 5.0 and win_rate > 0.6 and rug_rate < 0.1:
            tier = 'S'
        elif avg_max_gain > 3.0 and win_rate > 0.5 and rug_rate < 0.2:
            tier = 'A'
        elif avg_max_gain > 1.5 and win_rate > 0.4:
            tier = 'B'
        else:
            tier = 'C'

        # Insert or update
        self.cursor.execute('''
            INSERT INTO source_performance
            (source_name, total_calls, calls_traded, win_rate, avg_max_gain, rug_rate, tier, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name) DO UPDATE SET
                total_calls = excluded.total_calls,
                calls_traded = excluded.calls_traded,
                win_rate = excluded.win_rate,
                avg_max_gain = excluded.avg_max_gain,
                rug_rate = excluded.rug_rate,
                tier = excluded.tier,
                last_updated = excluded.last_updated
        ''', (source_name, total_calls, calls_traded, win_rate, avg_max_gain, rug_rate, tier, timestamp))

        self.conn.commit()

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Get all source performance statistics."""
        self.cursor.execute('''
            SELECT * FROM source_performance
            ORDER BY tier ASC, avg_max_gain DESC
        ''')
        return [dict(row) for row in self.cursor.fetchall()]

    def get_call_by_address(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get call information by contract address."""
        self.cursor.execute(
            'SELECT * FROM calls_received WHERE contract_address = ?',
            (contract_address,)
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    # Tracked Wallets Methods

    def insert_wallet(self, wallet_address: str, wallet_name: str, notes: str = "") -> int:
        """Insert a new tracked wallet."""
        timestamp = datetime.now().isoformat()

        try:
            self.cursor.execute('''
                INSERT INTO tracked_wallets
                (wallet_address, wallet_name, notes, date_added)
                VALUES (?, ?, ?, ?)
            ''', (wallet_address, wallet_name, notes, timestamp))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            # Wallet already exists
            return -1

    def remove_wallet(self, wallet_address: str) -> bool:
        """Remove a tracked wallet."""
        self.cursor.execute(
            'DELETE FROM tracked_wallets WHERE wallet_address = ?',
            (wallet_address,)
        )
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_all_wallets(self) -> List[Dict[str, Any]]:
        """Get all tracked wallets."""
        self.cursor.execute('''
            SELECT * FROM tracked_wallets
            ORDER BY tier ASC, avg_gain DESC
        ''')
        return [dict(row) for row in self.cursor.fetchall()]

    def get_wallet_by_address(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get a specific tracked wallet."""
        self.cursor.execute(
            'SELECT * FROM tracked_wallets WHERE wallet_address = ?',
            (wallet_address,)
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_wallet_performance(self, wallet_address: str, win_rate: float,
                                  avg_gain: float, total_buys: int):
        """Update wallet performance stats and calculate tier."""
        # Calculate tier based on performance
        if win_rate > 0.7 and avg_gain > 400:
            tier = 'S'
        elif win_rate > 0.6 and avg_gain > 250:
            tier = 'A'
        elif win_rate > 0.5 and avg_gain > 100:
            tier = 'B'
        else:
            tier = 'C'

        self.cursor.execute('''
            UPDATE tracked_wallets SET
                win_rate = ?,
                avg_gain = ?,
                total_tracked_buys = ?,
                tier = ?
            WHERE wallet_address = ?
        ''', (win_rate, avg_gain, total_buys, tier, wallet_address))
        self.conn.commit()

    def import_wallets_from_list(self, wallets: List[Dict[str, str]]) -> int:
        """Import multiple wallets from a list."""
        count = 0
        for wallet in wallets:
            wallet_id = self.insert_wallet(
                wallet_address=wallet.get('address', ''),
                wallet_name=wallet.get('name', ''),
                notes=wallet.get('notes', '')
            )
            if wallet_id > 0:
                count += 1
        return count

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Test database creation
    print("Testing database creation...")
    db = MemecoinDatabase("test_memecoin.db")
    print("✅ Database created successfully!")
    print(f"📁 Database file: {db.db_path}")

    # Test inserting a call
    call_id = db.insert_call(
        contract_address="TEST123ABC",
        token_symbol="TEST",
        token_name="Test Token",
        source="Test Source",
        blockchain="Solana"
    )
    print(f"✅ Test call inserted with ID: {call_id}")

    # Test inserting snapshot
    snapshot_data = {
        'liquidity_usd': 50000.0,
        'holder_count': 100,
        'top_holder_percent': 15.5,
        'top_10_holders_percent': 45.0,
        'token_age_hours': 2.5,
        'market_cap': 100000.0,
        'volume_24h': 25000.0,
        'price_usd': 0.001,
        'mint_authority_revoked': 1,
        'freeze_authority_revoked': 1,
        'rugcheck_score': 8.0,
        'safety_score': 8.5,
        'raw_data': {'test': 'data'}
    }
    snapshot_id = db.insert_snapshot(call_id, snapshot_data)
    print(f"✅ Test snapshot inserted with ID: {snapshot_id}")

    db.close()
    print("✅ All tests passed!")
