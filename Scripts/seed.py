"""
Seed script — one command to set up the full demo.

Usage:
    python scripts/seed.py

What it does:
    1. Waits for the API to be healthy
    2. Registers a client (dev-client) with email/password
    3. Imports test definitions from backend/config/test_definitions.yaml
    4. Runs the test engine and posts results to the API
    5. Prints the API key and login credentials

After running this, open http://localhost:3000 and log in with:
    Email: demo@dqf.dev
    Password: demo1234
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import requests

API_URL = os.getenv("DQF_API_URL", "http://localhost:8000")
EMAIL = "demo@dqf.dev"
PASSWORD = "demo1234"
CLIENT_NAME = "dev-client"
YAML_PATH = ROOT / "backend" / "config" / "test_definitions.yaml"


def wait_for_api(timeout=60):
    print(f"⏳ Waiting for API at {API_URL}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{API_URL}/api/v1/health", timeout=3)
            if r.status_code == 200:
                print("✅ API is ready\n")
                return
        except requests.ConnectionError:
            pass
        time.sleep(2)
    print("❌ API did not start in time")
    sys.exit(1)


def register_client():
    print(f"📝 Registering client '{CLIENT_NAME}'...")
    r = requests.post(
        f"{API_URL}/api/v1/clients",
        json={"name": CLIENT_NAME, "email": EMAIL, "password": PASSWORD},
    )
    if r.status_code == 201:
        data = r.json()
        api_key = data["api_key"]
        print(f"   Client ID: {data['id']}")
        print(f"   API Key:   {api_key}")
        return api_key
    elif r.status_code == 409:
        print(f"   Client already exists — logging in to verify credentials...")
        # Client exists; just verify login works
        lr = requests.post(
            f"{API_URL}/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        if lr.status_code == 200:
            print("   ✅ Login works, but API key is unknown (already registered).")
            print("   Set DQF_API_KEY env var manually if you need the engine to post results.")
            return None
        else:
            print(f"   ❌ Login failed: {lr.text}")
            sys.exit(1)
    else:
        print(f"   ❌ Registration failed: {r.status_code} {r.text}")
        sys.exit(1)


def import_tests(api_key):
    print(f"\n📦 Importing tests from {YAML_PATH.name}...")
    # Login to get JWT (import endpoint requires JWT, not API key)
    lr = requests.post(
        f"{API_URL}/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    if lr.status_code != 200:
        print(f"   ❌ Login failed: {lr.text}")
        sys.exit(1)
    token = lr.json()["access_token"]

    yaml_content = YAML_PATH.read_text(encoding="utf-8")
    r = requests.post(
        f"{API_URL}/api/v1/tests/import",
        json={"yaml_content": yaml_content},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code == 201:
        data = r.json()
        print(f"   ✅ Imported {data['imported']} tests, skipped {data['skipped']}")
    else:
        print(f"   ❌ Import failed: {r.status_code} {r.text}")
        sys.exit(1)


def run_engine(api_key):
    if not api_key:
        print("\n⚠️  Skipping engine run — no API key (client was already registered)")
        return
    print("\n🚀 Running test engine...")
    env = os.environ.copy()
    env["DQF_API_URL"] = API_URL
    env["DQF_API_KEY"] = api_key
    result = subprocess.run(
        [sys.executable, str(ROOT / "backend" / "main.py")],
        env=env,
        cwd=str(ROOT),
    )
    if result.returncode == 0:
        print("\n✅ Engine completed successfully")
    else:
        print(f"\n❌ Engine failed with exit code {result.returncode}")


def main():
    print("=" * 60)
    print("  DQF Seed Script — Setting up demo environment")
    print("=" * 60)
    print()

    wait_for_api()
    api_key = register_client()
    import_tests(api_key)
    run_engine(api_key)

    print()
    print("=" * 60)
    print("  ✅ Setup complete!")
    print("=" * 60)
    print()
    print("  Dashboard:  http://localhost:3000")
    print("  API docs:   http://localhost:8000/docs")
    print()
    print("  Login with:")
    print(f"    Email:    {EMAIL}")
    print(f"    Password: {PASSWORD}")
    if api_key:
        print()
        print(f"  API Key (for engine): {api_key}")
        print(f"  To re-run engine:     DQF_API_KEY={api_key}")
    print()


if __name__ == "__main__":
    main()
