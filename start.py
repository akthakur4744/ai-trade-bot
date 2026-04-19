#!/usr/bin/env python3
"""One-click start for Insight-Alpha.

Usage: python start.py

Opens the dashboard in your browser. Login with Zerodha and start trading.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

from src.web.app import main

if __name__ == "__main__":
    main()
