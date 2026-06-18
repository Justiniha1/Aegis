"""Provision a new client account (operator tool).

Creates a client on the dashboard API and prints the one-time API key plus the
dashboard login. Use this to onboard a paying client; the create endpoint is gated
behind COMET_ADMIN_TOKEN in production, so this script sends that header.

Usage:
    COMET_API_URL=https://your-api.up.railway.app \
    COMET_ADMIN_TOKEN=... \
    python Scripts/provision_client.py --name "Acme Corp" --email ops@acme.com --password "<temp-pw>"

The client logs into the dashboard with the email/password, and puts the printed
API key in their environment (COMET_API_KEY) for the CLI/engine.
"""

import argparse
import os
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision a new Comet client.")
    parser.add_argument("--name", required=True, help="Client/company name (unique)")
    parser.add_argument("--email", required=True, help="Login email (unique)")
    parser.add_argument("--password", required=True, help="Initial dashboard password")
    args = parser.parse_args()

    api_url = os.getenv("COMET_API_URL") or os.getenv("DQF_API_URL")
    admin_token = os.getenv("COMET_ADMIN_TOKEN", "")
    if not api_url:
        print("Set COMET_API_URL to the dashboard API base URL.", file=sys.stderr)
        return 2
    if not admin_token:
        print("Set COMET_ADMIN_TOKEN (must match the value on the API service).", file=sys.stderr)
        return 2

    resp = requests.post(
        f"{api_url.rstrip('/')}/api/v1/clients",
        json={"name": args.name, "email": args.email, "password": args.password},
        headers={"X-Admin-Token": admin_token},
        timeout=30,
    )

    if resp.status_code == 201:
        data = resp.json()
        print("Client provisioned.")
        print(f"  Name:     {data['name']}")
        print(f"  Email:    {args.email}")
        print(f"  Password: {args.password}  (share securely; have them change it)")
        print(f"  API key:  {data['api_key']}  (shown ONCE — give to the client for COMET_API_KEY)")
        return 0

    if resp.status_code == 403:
        print("Rejected: admin token missing or incorrect.", file=sys.stderr)
    elif resp.status_code == 409:
        print(f"Rejected: a client with that name or email already exists.", file=sys.stderr)
    else:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except ValueError:
            detail = resp.text
        print(f"Failed (HTTP {resp.status_code}): {detail}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
