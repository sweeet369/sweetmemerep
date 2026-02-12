#!/usr/bin/env python3
"""
Memecoin Trading Analyzer - Web Interface
A simple Flask web application for viewing and managing token analysis.
"""

import os
import sys
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

# Import existing modules
from database import MemecoinDatabase
from data_fetcher import MemecoinDataFetcher
from display import get_safety_rating, get_tier_emoji

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database and fetcher
db = MemecoinDatabase()
fetcher = MemecoinDataFetcher()

# Supported blockchains
BLOCKCHAINS = [
    ('solana', 'Solana'),
    ('base', 'Base'),
    ('ethereum', 'Ethereum'),
    ('bsc', 'BSC'),
    ('polygon', 'Polygon'),
    ('arbitrum', 'Arbitrum')
]


@app.route('/')
def dashboard():
    """Main dashboard showing watchlist and stats."""
    # Get watchlist tokens
    watchlist = get_watchlist_tokens()
    
    # Get source statistics
    sources = db.get_all_sources()
    
    # Calculate summary stats
    total_calls = len(watchlist)
    active_trades = sum(1 for w in watchlist if w['decision'] == 'TRADE')
    watching = sum(1 for w in watchlist if w['decision'] == 'WATCH')
    
    return render_template('dashboard.html',
                         watchlist=watchlist,
                         sources=sources,
                         total_calls=total_calls,
                         active_trades=active_trades,
                         watching=watching,
                         blockchains=BLOCKCHAINS)


@app.route('/token/<int:call_id>')
def token_detail(call_id):
    """Show detailed view of a specific token."""
    # Get token data
    token = get_token_by_id(call_id)
    if not token:
        flash('Token not found', 'error')
        return redirect(url_for('dashboard'))
    
    # Get performance history
    history = get_performance_history(call_id)
    
    # Get latest performance data
    performance = get_token_performance(call_id)
    
    return render_template('token_detail.html',
                         token=token,
                         history=history,
                         performance=performance,
                         safety_rating=get_safety_rating(token.get('safety_score', 0)))


@app.route('/add_token', methods=['GET', 'POST'])
def add_token():
    """Add a new token for analysis."""
    if request.method == 'POST':
        contract_address = request.form.get('contract_address', '').strip()
        source = request.form.get('source', '').strip()
        blockchain = request.form.get('blockchain', 'solana')
        
        if not contract_address:
            flash('Contract address is required', 'error')
            return redirect(url_for('add_token'))
        
        if not source:
            flash('Source is required', 'error')
            return redirect(url_for('add_token'))
        
        try:
            # Fetch token data
            print(f"🔍 Analyzing {contract_address} on {blockchain}...")
            data = fetcher.fetch_all_data(contract_address, blockchain=blockchain)
            
            if not data:
                flash('Failed to fetch token data. Please check the contract address.', 'error')
                return redirect(url_for('add_token'))
            
            # Insert into database
            call_id = db.insert_call(
                contract_address=contract_address,
                token_symbol=data.get('token_symbol', 'UNKNOWN'),
                token_name=data.get('token_name', 'Unknown Token'),
                source=source,
                blockchain=blockchain
            )
            
            # Insert snapshot
            db.insert_snapshot(call_id, data)
            
            # Insert initial decision (WATCH by default)
            db.insert_decision(
                call_id=call_id,
                decision='WATCH',
                trade_size_usd=None,
                entry_price=None,
                reasoning_notes=f"Added via web interface. Source: {source}",
                emotional_state='neutral',
                confidence_level=5,
                chart_assessment='Initial analysis'
            )

            # Create initial time-series point at call time.
            call_price = data.get('price_usd')
            db.insert_performance_history(call_id, {
                'decision_status': 'WATCH',
                'reference_price': call_price,
                'price_usd': call_price,
                'liquidity_usd': data.get('liquidity_usd'),
                'total_liquidity': data.get('total_liquidity') or data.get('liquidity_usd'),
                'market_cap': data.get('market_cap'),
                'gain_loss_pct': 0.0 if call_price else None,
                'price_change_pct': None,
                'liquidity_change_pct': None,
                'market_cap_change_pct': None,
                'token_still_alive': 'yes',
                'rug_pull_occurred': None
            })
            
            flash(f"✅ Token added successfully! {data.get('token_symbol')} is now on your watchlist.", 'success')
            return redirect(url_for('token_detail', call_id=call_id))
            
        except Exception as e:
            flash(f'Error adding token: {str(e)}', 'error')
            return redirect(url_for('add_token'))
    
    return render_template('add_token.html', blockchains=BLOCKCHAINS)


@app.route('/update_decision/<int:call_id>', methods=['POST'])
def update_decision(call_id):
    """Update the decision for a token (TRADE/PASS/WATCH)."""
    decision = request.form.get('decision')
    notes = request.form.get('notes', '')
    
    if decision not in ['TRADE', 'PASS', 'WATCH']:
        flash('Invalid decision', 'error')
        return redirect(url_for('token_detail', call_id=call_id))
    
    try:
        # Get current token data
        token = get_token_by_id(call_id)
        if not token:
            flash('Token not found', 'error')
            return redirect(url_for('dashboard'))

        current_decision = token.get('decision')
        call_price = token.get('price_usd')
        trade_entry_price = token.get('trade_entry_price')
        checkpoint_price = None
        checkpoint_liquidity = None
        checkpoint_total_liquidity = None
        checkpoint_mcap = None

        # Capture fresh market data for transition checkpoints.
        try:
            live = fetcher.fetch_birdeye_data(
                token['contract_address'],
                blockchain=(token.get('blockchain') or 'solana').lower()
            )
            if live:
                checkpoint_price = live.get('price_usd')
                checkpoint_liquidity = live.get('liquidity_usd')
                checkpoint_total_liquidity = live.get('total_liquidity') or live.get('liquidity_usd')
                checkpoint_mcap = live.get('market_cap')
        except Exception:
            pass

        if decision == 'TRADE' and current_decision != 'TRADE':
            # Use current market price for trade entry, not call price.
            new_entry_price = checkpoint_price or call_price
            entry_timestamp = datetime.now().isoformat()
            db._execute('''
                UPDATE my_decisions
                SET my_decision = ?, reasoning_notes = ?, entry_price = ?, entry_timestamp = ?
                WHERE call_id = ?
            ''', (decision, notes, new_entry_price, entry_timestamp, call_id))
            trade_entry_price = new_entry_price
        else:
            db._execute('''
                UPDATE my_decisions
                SET my_decision = ?, reasoning_notes = ?
                WHERE call_id = ?
            ''', (decision, notes, call_id))

        # Record a decision-transition checkpoint so history is continuous
        # up to the moment of PASS or TRADE conversion.
        if decision != current_decision:
            reference_price = trade_entry_price if decision == 'TRADE' else call_price
            gain_loss = None
            if checkpoint_price and reference_price:
                gain_loss = ((checkpoint_price - reference_price) / reference_price) * 100

            db.insert_performance_history(call_id, {
                'decision_status': decision,
                'reference_price': reference_price,
                'price_usd': checkpoint_price,
                'liquidity_usd': checkpoint_liquidity,
                'total_liquidity': checkpoint_total_liquidity,
                'market_cap': checkpoint_mcap,
                'gain_loss_pct': gain_loss,
                'price_change_pct': None,
                'liquidity_change_pct': None,
                'market_cap_change_pct': None,
                'token_still_alive': 'yes' if checkpoint_price else 'unknown',
                'rug_pull_occurred': None
            })

        # Commit both the decision update and history insert atomically.
        db.conn.commit()

        flash(f'Decision updated to {decision}', 'success')

    except Exception as e:
        # Rollback undoes both the decision change AND the history insert.
        db.conn.rollback()
        flash(f'Error updating decision: {str(e)}', 'error')
    
    return redirect(url_for('token_detail', call_id=call_id))


@app.route('/sources')
def sources():
    """View all sources and their performance."""
    sources = db.get_all_sources()
    return render_template('sources.html', sources=sources)


@app.route('/api/refresh_token/<int:call_id>', methods=['POST'])
def refresh_token(call_id):
    """API endpoint to refresh token data."""
    try:
        token = get_token_by_id(call_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'})
        
        # Fetch fresh data
        data = fetcher.fetch_birdeye_data(token['contract_address'], blockchain=token['blockchain'].lower())
        
        if data:
            # Update performance tracking
            db.insert_or_update_performance(call_id, {
                'current_mcap': data.get('market_cap'),
                'current_liquidity': data.get('liquidity_usd'),
                'token_still_alive': 'yes'
            })
            
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'error': 'Failed to fetch data'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def get_watchlist_tokens():
    """Get all tokens on watchlist with their latest data."""
    db.cursor.execute('''
        SELECT 
            c.call_id,
            c.contract_address,
            c.token_symbol,
            c.token_name,
            c.source,
            c.blockchain,
            s.snapshot_timestamp,
            s.price_usd as call_price,
            d.entry_price as trade_entry_price,
            s.liquidity_usd,
            s.market_cap,
            s.safety_score,
            d.my_decision as decision,
            p.current_mcap,
            p.current_liquidity,
            p.max_gain_observed,
            p.token_still_alive,
            p.rug_pull_occurred
        FROM calls_received c
        JOIN initial_snapshot s ON c.call_id = s.call_id
        JOIN my_decisions d ON c.call_id = d.call_id
        LEFT JOIN performance_tracking p ON c.call_id = p.call_id
        WHERE d.my_decision IN ('WATCH', 'TRADE')
        ORDER BY s.snapshot_timestamp DESC
    ''')
    
    rows = db.cursor.fetchall()
    tokens = []
    for row in rows:
        token = dict(row)
        
        # Calculate current gain/loss if we have current price
        if token.get('current_mcap') and token.get('market_cap'):
            token['mcap_change_pct'] = ((token['current_mcap'] - token['market_cap']) / token['market_cap']) * 100
        else:
            token['mcap_change_pct'] = None
        
        # Format timestamps
        if token.get('snapshot_timestamp'):
            try:
                dt = datetime.fromisoformat(str(token['snapshot_timestamp']).replace('Z', '+00:00'))
                token['time_ago'] = format_time_ago(dt)
            except:
                token['time_ago'] = 'Unknown'
        
        tokens.append(token)
    
    return tokens


def get_token_by_id(call_id):
    """Get token data by call_id."""
    query = db._placeholder()
    db.cursor.execute(f'''
        SELECT 
            c.*,
            s.*,
            d.my_decision as decision,
            d.entry_price as trade_entry_price,
            d.entry_timestamp as trade_entry_timestamp,
            d.actual_exit_price,
            d.reasoning_notes,
            d.emotional_state,
            d.confidence_level
        FROM calls_received c
        JOIN initial_snapshot s ON c.call_id = s.call_id
        JOIN my_decisions d ON c.call_id = d.call_id
        WHERE c.call_id = {query}
    ''', (call_id,))
    
    row = db.cursor.fetchone()
    return dict(row) if row else None


def get_token_performance(call_id):
    """Get performance data for a token."""
    query = db._placeholder()
    db.cursor.execute(f'''
        SELECT * FROM performance_tracking WHERE call_id = {query}
    ''', (call_id,))
    
    row = db.cursor.fetchone()
    return dict(row) if row else None


def get_performance_history(call_id):
    """Get performance history for a token."""
    query = db._placeholder()
    db.cursor.execute(f'''
        SELECT * FROM performance_history 
        WHERE call_id = {query}
        ORDER BY timestamp DESC
    ''', (call_id,))
    
    rows = db.cursor.fetchall()
    return [dict(row) for row in rows]


def format_time_ago(dt):
    """Format datetime as 'X minutes/hours/days ago'."""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return 'Just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours} hour{"s" if hours > 1 else ""} ago'
    else:
        days = int(seconds / 86400)
        return f'{days} day{"s" if days > 1 else ""} ago'


@app.template_filter('format_currency')
def format_currency_filter(value):
    """Template filter to format currency values."""
    if value is None:
        return 'N/A'
    
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f'${value/1_000_000_000:.2f}B'
        elif value >= 1_000_000:
            return f'${value/1_000_000:.2f}M'
        elif value >= 1_000:
            return f'${value/1_000:.2f}K'
        else:
            return f'${value:.2f}'
    except:
        return str(value)


@app.template_filter('format_number')
def format_number_filter(value):
    """Template filter to format large numbers."""
    if value is None:
        return 'N/A'
    
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f'{value/1_000_000_000:.2f}B'
        elif value >= 1_000_000:
            return f'{value/1_000_000:.2f}M'
        elif value >= 1_000:
            return f'{value/1_000:.1f}K'
        else:
            return f'{value:.0f}'
    except:
        return str(value)


if __name__ == '__main__':
    print("🚀 Starting Memecoin Trading Analyzer Web Interface")
    print("📱 Open your browser and go to: http://localhost:5001")
    print("⚠️  Press Ctrl+C to stop the server\n")
    
    # Run in debug mode for development
    import os
    port = int(os.environ.get('PORT', 5001))  # Use 5001 if 5000 is taken
    app.run(host='0.0.0.0', port=port, debug=True)
