#!/usr/bin/env python3
"""
Demo the watchlist feature without interactive input
"""

from analyzer import MemecoinAnalyzer

def demo_watchlist():
    """Show watchlist without running the full interactive menu."""
    print("\n" + "="*60)
    print("🪙  MEMECOIN ANALYZER - WATCHLIST DEMO")
    print("="*60)

    analyzer = MemecoinAnalyzer()
    analyzer.view_watchlist()
    analyzer.db.close()

    print("\n💡 In the real analyzer, this is option [3] in the menu!")
    print()

if __name__ == "__main__":
    demo_watchlist()
