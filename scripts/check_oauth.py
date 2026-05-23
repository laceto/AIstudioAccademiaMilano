"""
OAuth pre-check hook — AI Studio Accademia Milano

Fires before any Gmail API call (PreToolUse hook).
Verifies an active session token exists, prompts user if not.
Exit code 0 = proceed. Exit code 1 = block tool use.
"""

import argparse
import os
import sys


def check_gmail_token() -> bool:
    token = os.environ.get("GMAIL_OAUTH_SESSION_TOKEN")
    return bool(token and token != "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    args = parser.parse_args()

    if args.provider == "gmail":
        if check_gmail_token():
            print("[check_oauth] Gmail OAuth token active. Proceeding.")
            sys.exit(0)
        else:
            print("[check_oauth] No Gmail OAuth token found.")
            print("[check_oauth] Stacy will prompt user for OAuth before continuing.")
            sys.exit(1)
    else:
        print(f"[check_oauth] Unknown provider: {args.provider}")
        sys.exit(1)


if __name__ == "__main__":
    main()
