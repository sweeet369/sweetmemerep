"""
Test configuration - adds project root to Python path so tests can import core modules.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
