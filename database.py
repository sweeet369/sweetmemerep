from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection, cursor as PgCursor
    from sqlite3 import Connection as SqliteConnection, Cursor as SqliteCursor

# Import structured logging
from app_logger import db_logger, log_db_operation

# Import centralized config
from config import DATABASE_URL, DEFAULT_DB_PATH, HIT_THRESHOLD

# Connection pool for PostgreSQL (initialized lazily)
_pg_connection_pool = None


def get_pg_pool():
    """Get or create PostgreSQL connection pool."""
    global _pg_connection_pool
    if _pg_connection_pool is None and DATABASE_URL:
        from psycopg2.pool import ThreadedConnectionPool
        _pg_connection_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=DATABASE_URL
        )
        db_logger.info("PostgreSQL connection pool initialized (min=2, max=10)")
    return _pg_connection_pool


def get_db_connection():
    """Get database connection based on environment."""
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        return conn, 'postgres'
    else:
        import sqlite3
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'


class MemecoinDatabase:
    """Database manager for memecoin trading analyzer. Supports SQLite and PostgreSQL."""

    # Type hints for instance attributes
    db_type: str
    db_path: str
    conn: PgConnection | SqliteConnection
    cursor: PgCursor | SqliteCursor
    _using_pool: bool

    def __init__(self, db_path: str | None = None, use_pool: bool = True):
        """Initialize database connection.

        Args:
            db_path: Path for SQLite database (ignored if DATABASE_URL is set)
            use_pool: Whether to use connection pooling for PostgreSQL
        """
        self._using_pool = False

        if DATABASE_URL:
            # Use PostgreSQL (Supabase)
            from psycopg2.extras import RealDictCursor

            if use_pool:
                pool = get_pg_pool()
                if pool:
                    self.conn = pool.getconn()
                    self._using_pool = True
                    db_logger.debug("Got connection from pool")
                else:
                    import psycopg2
                    self.conn = psycopg2.connect(DATABASE_URL)
            else:
                import psycopg2
                self.conn = psycopg2.connect(DATABASE_URL)

            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            self.db_type = 'postgres'
            self.db_path = DATABASE_URL[:50] + '...'  # Truncate for display
        else:
            # Use SQLite
            import sqlite3
            self.db_path = db_path or DEFAULT_DB_PATH
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.db_type = 'sqlite'
            self.create_tables()

    def _placeholder(self) -> str:
        """Return the correct placeholder for the database type."""
        return '%s' if self.db_type == 'postgres' else '?'

    def _placeholders(self, count: int) -> str:
        """Return multiple placeholders."""
        p = self._placeholder()
        return ', '.join([p] * count)

    def _to_bool(self, value: str | bool | None) -> bool | str | None:
        """Convert boolean value to appropriate type for database.

        PostgreSQL uses native BOOLEAN, SQLite uses TEXT 'yes'/'no'.
        """
        if value is None:
            return None
        if self.db_type == 'postgres':
            # PostgreSQL: use native boolean
            if isinstance(value, bool):
                return value
            return value == 'yes' or value is True
        else:
            # SQLite: use 'yes'/'no' strings
            if isinstance(value, bool):
                return 'yes' if value else 'no'
            return value  # Already a string

    def _from_bool(self, value: bool | str | None) -> bool:
        """Convert database boolean to Python bool.

        Handles both PostgreSQL BOOLEAN and SQLite TEXT 'yes'/'no'.
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return value == 'yes'

    def create_tables(self) -> None:
        """Create all database tables if they don't exist (SQLite only - PostgreSQL uses migration)."""
        if self.db_type == 'postgres':
            return  # Tables created via SQL migration in Supabase

        # SQLite table creation (same as before)
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
                price_vs_atl_percent REAL,
                buy_count_24h INTEGER,
                sell_count_24h INTEGER,
                price_change_5m REAL,
                price_change_1h REAL,
                price_change_24h REAL,
                all_time_high REAL,
                all_time_low REAL,
                liquidity_locked_percent REAL,
                main_pool_liquidity REAL,
                total_liquidity REAL,
                main_pool_dex TEXT,
                FOREIGN KEY (call_id) REFERENCES calls_received (call_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS my_decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                timestamp_decision TEXT NOT NULL,
                my_decision TEXT NOT NULL,
                trade_size_usd REAL,
                entry_price REAL,
                entry_timestamp TEXT,
                reasoning_notes TEXT,
                emotional_state TEXT,
                confidence_level INTEGER,
                chart_assessment TEXT,
                actual_exit_price REAL,
                hold_duration_hours REAL,
                FOREIGN KEY (call_id) REFERENCES calls_received (call_id)
            )
        ''')

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
                checkpoint_type TEXT,
                max_price_since_entry REAL,
                min_price_since_entry REAL,
                FOREIGN KEY (call_id) REFERENCES calls_received (call_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_performance (
                source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT UNIQUE NOT NULL,
                total_calls INTEGER DEFAULT 0,
                calls_traded INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                avg_max_gain REAL DEFAULT 0.0,
                rug_rate REAL DEFAULT 0.0,
                hit_rate REAL DEFAULT 0.0,
                tier TEXT DEFAULT 'C',
                last_updated TEXT NOT NULL
            )
        ''')

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

        # Create indexes for foreign keys and frequently queried columns
        # This dramatically improves JOIN and lookup performance
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_initial_snapshot_call_id ON initial_snapshot(call_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_my_decisions_call_id ON my_decisions(call_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_tracking_call_id ON performance_tracking(call_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_calls_received_source ON calls_received(source)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_calls_received_contract ON calls_received(contract_address)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracked_wallets_address ON tracked_wallets(wallet_address)')

        self.conn.commit()
        db_logger.info("SQLite tables and indexes created/verified")

    def _execute(self, query: str, params: tuple | None = None) -> None:
        """Execute a query with proper placeholder substitution."""
        if self.db_type == 'postgres':
            # Replace ? with %s for PostgreSQL
            query = query.replace('?', '%s')
        self.cursor.execute(query, params or ())

    def _fetchone(self) -> Dict[str, Any] | None:
        """Fetch one result as dict."""
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetchall(self) -> List[Dict[str, Any]]:
        """Fetch all results as list of dicts."""
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def insert_call(self, contract_address: str, token_symbol: str, token_name: str,
                    source: str, blockchain: str = "Solana") -> int:
        """Insert a new call received record."""
        timestamp = datetime.now().isoformat()

        try:
            if self.db_type == 'postgres':
                self._execute('''
                    INSERT INTO calls_received
                    (timestamp_received, contract_address, token_symbol, token_name, source, blockchain)
                    VALUES (?, ?, ?, ?, ?, ?)
                    RETURNING call_id
                ''', (timestamp, contract_address, token_symbol, token_name, source, blockchain))
                result = self._fetchone()
                self.conn.commit()
                return result['call_id']
            else:
                self._execute('''
                    INSERT INTO calls_received
                    (timestamp_received, contract_address, token_symbol, token_name, source, blockchain)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (timestamp, contract_address, token_symbol, token_name, source, blockchain))
                self.conn.commit()
                return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            # Check if this is a unique constraint violation (contract already exists)
            error_str = str(e).lower()
            if 'unique' in error_str or 'duplicate' in error_str:
                # Contract address already exists, return existing call_id
                self._execute(
                    'SELECT call_id FROM calls_received WHERE contract_address = ?',
                    (contract_address,)
                )
                result = self._fetchone()
                if result:
                    return result['call_id']
            # Log unexpected errors
            db_logger.error(f"Failed to insert call for {contract_address}: {e}")
            return -1

    def insert_snapshot(self, call_id: int, data: Dict[str, Any]) -> int:
        """Insert initial snapshot data."""
        timestamp = datetime.now().isoformat()

        params = (
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
            data.get('liquidity_locked_percent'),
            data.get('main_pool_liquidity'),
            data.get('total_liquidity'),
            data.get('main_pool_dex')
        )

        if self.db_type == 'postgres':
            self._execute('''
                INSERT INTO initial_snapshot (
                    call_id, snapshot_timestamp, liquidity_usd, holder_count,
                    top_holder_percent, top_10_holders_percent, token_age_hours,
                    market_cap, volume_24h, price_usd, mint_authority_revoked,
                    freeze_authority_revoked, rugcheck_score, safety_score, raw_data,
                    price_vs_atl_percent, buy_count_24h, sell_count_24h,
                    price_change_5m, price_change_1h, price_change_24h,
                    all_time_high, all_time_low, liquidity_locked_percent,
                    main_pool_liquidity, total_liquidity, main_pool_dex
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING snapshot_id
            ''', params)
            result = self._fetchone()
            self.conn.commit()
            return result['snapshot_id']
        else:
            self._execute('''
                INSERT INTO initial_snapshot (
                    call_id, snapshot_timestamp, liquidity_usd, holder_count,
                    top_holder_percent, top_10_holders_percent, token_age_hours,
                    market_cap, volume_24h, price_usd, mint_authority_revoked,
                    freeze_authority_revoked, rugcheck_score, safety_score, raw_data,
                    price_vs_atl_percent, buy_count_24h, sell_count_24h,
                    price_change_5m, price_change_1h, price_change_24h,
                    all_time_high, all_time_low, liquidity_locked_percent,
                    main_pool_liquidity, total_liquidity, main_pool_dex
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', params)
            self.conn.commit()
            return self.cursor.lastrowid

    def insert_decision(self, call_id: int, decision: str, trade_size_usd: Optional[float],
                       entry_price: Optional[float], reasoning_notes: str,
                       emotional_state: str, confidence_level: int,
                       chart_assessment: Optional[str] = None,
                       entry_timestamp: Optional[str] = None) -> int:
        """Insert user's trading decision."""
        timestamp = datetime.now().isoformat()

        if decision == 'TRADE' and not entry_timestamp:
            entry_timestamp = timestamp

        params = (call_id, timestamp, decision, trade_size_usd, entry_price, entry_timestamp,
                  reasoning_notes, emotional_state, confidence_level, chart_assessment)

        if self.db_type == 'postgres':
            self._execute('''
                INSERT INTO my_decisions (
                    call_id, timestamp_decision, my_decision, trade_size_usd,
                    entry_price, entry_timestamp, reasoning_notes, emotional_state,
                    confidence_level, chart_assessment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING decision_id
            ''', params)
            result = self._fetchone()
            self.conn.commit()
            return result['decision_id']
        else:
            self._execute('''
                INSERT INTO my_decisions (
                    call_id, timestamp_decision, my_decision, trade_size_usd,
                    entry_price, entry_timestamp, reasoning_notes, emotional_state,
                    confidence_level, chart_assessment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', params)
            self.conn.commit()
            return self.cursor.lastrowid

    def record_exit(self, call_id: int, exit_price: float) -> bool:
        """Record exit from a trade and calculate hold duration."""
        self._execute('''
            SELECT timestamp_decision FROM my_decisions
            WHERE call_id = ? AND my_decision = 'TRADE'
        ''', (call_id,))

        result = self._fetchone()
        if not result:
            return False

        entry_time = datetime.fromisoformat(result['timestamp_decision'])
        exit_time = datetime.now()
        hold_duration = (exit_time - entry_time).total_seconds() / 3600

        self._execute('''
            UPDATE my_decisions SET
                actual_exit_price = ?,
                hold_duration_hours = ?
            WHERE call_id = ? AND my_decision = 'TRADE'
        ''', (exit_price, hold_duration, call_id))

        self.conn.commit()
        return True

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades (TRADE decisions without exit recorded)."""
        self._execute('''
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
        return self._fetchall()

    def insert_or_update_performance(self, call_id: int, data: Dict[str, Any]) -> int:
        """Insert or update performance tracking data."""
        timestamp = datetime.now().isoformat()

        # Convert boolean fields to appropriate type for database
        token_alive = self._to_bool(data.get('token_still_alive'))
        rug_occurred = self._to_bool(data.get('rug_pull_occurred'))

        self._execute(
            'SELECT tracking_id FROM performance_tracking WHERE call_id = ?',
            (call_id,)
        )
        existing = self._fetchone()

        if existing:
            self._execute('''
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
                token_alive,
                rug_occurred,
                data.get('checkpoint_type'),
                data.get('max_price_since_entry'),
                data.get('min_price_since_entry'),
                call_id
            ))
            tracking_id = existing['tracking_id']
        else:
            params = (
                call_id, timestamp,
                data.get('price_1h_later'),
                data.get('price_24h_later'),
                data.get('price_7d_later'),
                data.get('price_30d_later'),
                data.get('current_mcap'),
                data.get('current_liquidity'),
                data.get('max_gain_observed'),
                data.get('max_loss_observed'),
                token_alive,
                rug_occurred,
                data.get('checkpoint_type'),
                data.get('max_price_since_entry'),
                data.get('min_price_since_entry')
            )

            if self.db_type == 'postgres':
                self._execute('''
                    INSERT INTO performance_tracking (
                        call_id, last_updated, price_1h_later, price_24h_later,
                        price_7d_later, price_30d_later, current_mcap, current_liquidity,
                        max_gain_observed, max_loss_observed, token_still_alive, rug_pull_occurred,
                        checkpoint_type, max_price_since_entry, min_price_since_entry
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING tracking_id
                ''', params)
                result = self._fetchone()
                tracking_id = result['tracking_id']
            else:
                self._execute('''
                    INSERT INTO performance_tracking (
                        call_id, last_updated, price_1h_later, price_24h_later,
                        price_7d_later, price_30d_later, current_mcap, current_liquidity,
                        max_gain_observed, max_loss_observed, token_still_alive, rug_pull_occurred,
                        checkpoint_type, max_price_since_entry, min_price_since_entry
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', params)
                tracking_id = self.cursor.lastrowid

        self.conn.commit()
        return tracking_id

    def update_source_performance(self, source_name: str) -> None:
        """Calculate and update source performance statistics for an individual source."""
        timestamp = datetime.now().isoformat()
        source_name = source_name.strip()

        self._execute('''
            SELECT
                c.call_id,
                d.my_decision,
                d.entry_price,
                d.actual_exit_price,
                p.max_gain_observed,
                p.rug_pull_occurred
            FROM calls_received c
            LEFT JOIN my_decisions d ON c.call_id = d.call_id
            LEFT JOIN performance_tracking p ON c.call_id = p.call_id
            WHERE c.source = ?
               OR c.source LIKE ?
               OR c.source LIKE ?
               OR c.source LIKE ?
        ''', (source_name, f'{source_name},%', f'%, {source_name}', f'%, {source_name},%'))

        calls = self._fetchall()
        total_calls = len(calls)
        calls_traded = sum(1 for c in calls if c['my_decision'] == 'TRADE')

        gains = [c['max_gain_observed'] for c in calls if c['max_gain_observed'] is not None and c['max_gain_observed'] > 0]
        avg_max_gain = sum(gains) / len(gains) if gains else 0.0

        # Handle both BOOLEAN (PostgreSQL) and TEXT 'yes'/'no' (SQLite)
        rugs = sum(1 for c in calls if self._from_bool(c['rug_pull_occurred']))
        rug_rate = rugs / total_calls if total_calls > 0 else 0.0

        traded_calls = [c for c in calls if c['my_decision'] == 'TRADE']
        exited_trades = [c for c in traded_calls
                        if c['actual_exit_price'] is not None
                        and c['actual_exit_price'] > 0
                        and c['entry_price'] is not None]
        wins = sum(1 for c in exited_trades if c['actual_exit_price'] > c['entry_price'])
        win_rate = wins / len(exited_trades) if exited_trades else 0.0

        hits = sum(1 for c in calls if c['max_gain_observed'] and c['max_gain_observed'] >= HIT_THRESHOLD)
        hit_rate = hits / total_calls if total_calls > 0 else 0.0

        if avg_max_gain > 5.0 and win_rate > 0.6 and rug_rate < 0.1:
            tier = 'S'
        elif avg_max_gain > 3.0 and win_rate > 0.5 and rug_rate < 0.2:
            tier = 'A'
        elif avg_max_gain > 1.5 and win_rate > 0.4:
            tier = 'B'
        else:
            tier = 'C'

        if self.db_type == 'postgres':
            self._execute('''
                INSERT INTO source_performance
                (source_name, total_calls, calls_traded, win_rate, avg_max_gain, rug_rate, hit_rate, tier, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    total_calls = EXCLUDED.total_calls,
                    calls_traded = EXCLUDED.calls_traded,
                    win_rate = EXCLUDED.win_rate,
                    avg_max_gain = EXCLUDED.avg_max_gain,
                    rug_rate = EXCLUDED.rug_rate,
                    hit_rate = EXCLUDED.hit_rate,
                    tier = EXCLUDED.tier,
                    last_updated = EXCLUDED.last_updated
            ''', (source_name, total_calls, calls_traded, win_rate, avg_max_gain, rug_rate, hit_rate, tier, timestamp))
        else:
            self._execute('''
                INSERT INTO source_performance
                (source_name, total_calls, calls_traded, win_rate, avg_max_gain, rug_rate, hit_rate, tier, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    total_calls = excluded.total_calls,
                    calls_traded = excluded.calls_traded,
                    win_rate = excluded.win_rate,
                    avg_max_gain = excluded.avg_max_gain,
                    rug_rate = excluded.rug_rate,
                    hit_rate = excluded.hit_rate,
                    tier = excluded.tier,
                    last_updated = excluded.last_updated
            ''', (source_name, total_calls, calls_traded, win_rate, avg_max_gain, rug_rate, hit_rate, tier, timestamp))

        self.conn.commit()

    def cleanup_combined_sources(self) -> int:
        """Remove combined source entries from source_performance table."""
        self._execute('''
            SELECT source_name FROM source_performance
            WHERE source_name LIKE '%,%'
        ''')
        combined_sources = [row['source_name'] for row in self._fetchall()]

        if not combined_sources:
            return 0

        # Batch delete instead of N+1 pattern - single query for all deletions
        placeholders = self._placeholders(len(combined_sources))
        self._execute(
            f'DELETE FROM source_performance WHERE source_name IN ({placeholders})',
            tuple(combined_sources)
        )

        self.conn.commit()
        db_logger.info(f"Cleaned up {len(combined_sources)} combined source entries")
        return len(combined_sources)

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Get all source performance statistics."""
        self._execute('''
            SELECT * FROM source_performance
            ORDER BY tier ASC, avg_max_gain DESC
        ''')
        return self._fetchall()

    def get_call_by_address(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get call information by contract address."""
        self._execute(
            'SELECT * FROM calls_received WHERE contract_address = ?',
            (contract_address,)
        )
        return self._fetchone()

    def insert_wallet(self, wallet_address: str, wallet_name: str, notes: str = "") -> int:
        """Insert a new tracked wallet."""
        timestamp = datetime.now().isoformat()

        try:
            if self.db_type == 'postgres':
                self._execute('''
                    INSERT INTO tracked_wallets
                    (wallet_address, wallet_name, notes, date_added)
                    VALUES (?, ?, ?, ?)
                    RETURNING wallet_id
                ''', (wallet_address, wallet_name, notes, timestamp))
                result = self._fetchone()
                self.conn.commit()
                return result['wallet_id']
            else:
                self._execute('''
                    INSERT INTO tracked_wallets
                    (wallet_address, wallet_name, notes, date_added)
                    VALUES (?, ?, ?, ?)
                ''', (wallet_address, wallet_name, notes, timestamp))
                self.conn.commit()
                return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            error_str = str(e).lower()
            if 'unique' in error_str or 'duplicate' in error_str:
                db_logger.warning(f"Wallet {wallet_address} already exists")
            else:
                db_logger.error(f"Failed to insert wallet {wallet_address}: {e}")
            return -1

    def remove_wallet(self, wallet_address: str) -> bool:
        """Remove a tracked wallet."""
        self._execute(
            'DELETE FROM tracked_wallets WHERE wallet_address = ?',
            (wallet_address,)
        )
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_all_wallets(self) -> List[Dict[str, Any]]:
        """Get all tracked wallets."""
        self._execute('''
            SELECT * FROM tracked_wallets
            ORDER BY tier ASC, avg_gain DESC
        ''')
        return self._fetchall()

    def get_wallet_by_address(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get a specific tracked wallet."""
        self._execute(
            'SELECT * FROM tracked_wallets WHERE wallet_address = ?',
            (wallet_address,)
        )
        return self._fetchone()

    def update_wallet_performance(self, wallet_address: str, win_rate: float,
                                  avg_gain: float, total_buys: int) -> None:
        """Update wallet performance stats and calculate tier."""
        if win_rate > 0.7 and avg_gain > 400:
            tier = 'S'
        elif win_rate > 0.6 and avg_gain > 250:
            tier = 'A'
        elif win_rate > 0.5 and avg_gain > 100:
            tier = 'B'
        else:
            tier = 'C'

        self._execute('''
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

    def close(self) -> None:
        """Close database connection or return to pool."""
        if self._using_pool:
            pool = get_pg_pool()
            if pool:
                pool.putconn(self.conn)
                db_logger.debug("Connection returned to pool")
                return
        self.conn.close()

    def __enter__(self) -> MemecoinDatabase:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    print("Testing database connection...")
    db = MemecoinDatabase()
    print(f"✅ Connected to: {db.db_type}")
    print(f"📁 Database: {db.db_path}")
    db.close()
    print("✅ Connection test passed!")
