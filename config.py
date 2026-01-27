"""
Centralized configuration for Memecoin Analyzer.

Loads .env once and exports all settings used across modules.
"""

import os

# Load environment variables from .env file (if it exists)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass  # dotenv not installed, will use environment variables directly

# Database
DATABASE_URL = os.environ.get('DATABASE_URL')
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memecoin_analyzer.db")

# API Keys
BIRDEYE_API_KEY = os.environ.get('BIRDEYE_API_KEY')

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# Trading thresholds
HIT_THRESHOLD = 50.0  # Minimum gain % to count as hit
