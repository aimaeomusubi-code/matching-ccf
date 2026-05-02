#!/usr/bin/env python3
"""
One-time OAuth2 setup script. Run this locally to generate GMAIL_REFRESH_TOKEN.

Prerequisites:
  1. Go to https://console.cloud.google.com
  2. Create a project (or select existing)
  3. Enable "Gmail API"
  4. Create an OAuth2 client ID (Application type: Desktop app)
  5. Download the JSON and save it as credentials.json in this directory

Usage:
  python setup_auth.py
"""
import json
import os
import sys

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDENTIALS_FILE = "credentials.json"


def main() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: Required packages not installed.")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found.\n")
        print("Steps to get it:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. APIs & Services > Credentials")
        print("  3. Create OAuth2 Client ID (Desktop app)")
        print(f"  4. Download JSON and save as {CREDENTIALS_FILE}")
        sys.exit(1)

    print("Opening browser for Gmail authorization...")
    print("(If the browser doesn't open, follow the URL printed in the terminal)\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080)

    print("\n" + "=" * 60)
    print("SUCCESS! Copy these values to GitHub Secrets:")
    print("=" * 60)
    print(f"\nGMAIL_CLIENT_ID     = {creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET = {creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN = {creds.refresh_token}")
    print(f"\nGMAIL_USER_EMAIL    = <your gmail address>")
    print(f"ANTHROPIC_API_KEY   = <from https://console.anthropic.com>")
    print("\n" + "=" * 60)

    # Also save to .env for local testing
    env_content = (
        f"GMAIL_CLIENT_ID={creds.client_id}\n"
        f"GMAIL_CLIENT_SECRET={creds.client_secret}\n"
        f"GMAIL_REFRESH_TOKEN={creds.refresh_token}\n"
        f"GMAIL_USER_EMAIL=\n"
        f"ANTHROPIC_API_KEY=\n"
    )
    with open(".env", "w") as f:
        f.write(env_content)
    print("\nAlso saved to .env (fill in GMAIL_USER_EMAIL and ANTHROPIC_API_KEY)")
    print("WARNING: .env is in .gitignore — never commit it!")

    # Save raw tokens as backup
    with open(".oauth_tokens.json", "w") as f:
        json.dump(
            {
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "refresh_token": creds.refresh_token,
            },
            f,
            indent=2,
        )
    print(".oauth_tokens.json saved as backup (also in .gitignore)")


if __name__ == "__main__":
    main()
