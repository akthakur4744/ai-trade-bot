"""Kite Connect authentication helper.

Run this script daily before market open to generate an access token.

Usage:
    python scripts/kite_auth.py

The script will:
1. Print the Zerodha login URL
2. Wait for you to paste the redirect URL (contains request_token)
3. Exchange it for an access token and cache it for the day
"""

import os
import sys
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from src.data.kite_client import KiteClient


def main() -> None:
    client = KiteClient()

    # Check if we already have today's token
    try:
        client.authenticate()
        print("Already authenticated for today.")
        return
    except ValueError:
        pass

    # Need to log in
    print(f"\nOpen this URL in your browser:\n\n{client.login_url}\n")
    print("After logging in, you'll be redirected. Paste the full redirect URL here:")

    redirect_url = input("\nRedirect URL: ").strip()

    # Extract request_token from URL
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    request_token = params.get("request_token", [None])[0]

    if not request_token:
        print("Error: Could not extract request_token from URL")
        sys.exit(1)

    client.authenticate(request_token=request_token)
    print("\nAuthentication successful! Token cached for today.")


if __name__ == "__main__":
    main()
