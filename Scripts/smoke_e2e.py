#!/usr/bin/env python3
"""
Week 1 E2E smoke test.

Requirements:
  - Stack running: make start
  - .env has AEGIS_API_KEY and AEGIS_ENCRYPTION_KEY
  - aegis CLI installed: pip install -e ".[dev]"

Run: python Scripts/smoke_e2e.py
"""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("DQF_API_URL", "http://localhost:8000")
API_KEY = os.getenv("AEGIS_API_KEY") or os.getenv("DQF_API_KEY")

if not API_KEY:
    print("AEGIS_API_KEY not set in .env — aborting")
    sys.exit(1)

HEADERS = {"X-Api-Key": API_KEY}
PASS = "✓"
FAIL = "✗"
_failed = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  {PASS} {label}")
    else:
        msg = f"  {FAIL} {label}" + (f"  ({detail})" if detail else "")
        print(msg)
        _failed.append(label)


def cli(*args, cwd=None) -> subprocess.CompletedProcess:
    env = {**os.environ, "AEGIS_API_KEY": API_KEY}
    return subprocess.run(
        ["aegis", *args], capture_output=True, text=True, cwd=cwd, env=env
    )


print("\n── Week 1 E2E Smoke Test ──────────────────────────────────")

# ── 1. API health ──────────────────────────────────────────────────────────────
print("\n[1] API health")
try:
    r = requests.get(f"{API_URL}/api/v1/health", timeout=5)
    check("GET /api/v1/health → 200", r.status_code == 200, r.text)
except requests.ConnectionError:
    print(f"  {FAIL} Cannot reach {API_URL} — is 'make start' running?")
    sys.exit(1)

# ── 2. Connection profiles CRUD ────────────────────────────────────────────────
print("\n[2] Connection profiles CRUD")

# Create
r = requests.post(f"{API_URL}/api/v1/profiles", json={
    "name": "smoke-test",
    "connection_url": "sqlite:///./smoke_test.db",
    "db_type": "sqlite",
}, headers=HEADERS)
check("POST /api/v1/profiles → 201", r.status_code == 201, r.text)
profile_id = r.json().get("id") if r.status_code == 201 else None

# List
r = requests.get(f"{API_URL}/api/v1/profiles", headers=HEADERS)
check(
    "GET /api/v1/profiles includes smoke-test",
    any(p["name"] == "smoke-test" for p in r.json()),
)

# Duplicate → 409
r = requests.post(f"{API_URL}/api/v1/profiles", json={
    "name": "smoke-test", "connection_url": "sqlite:///./x.db", "db_type": "sqlite",
}, headers=HEADERS)
check("Duplicate profile → 409", r.status_code == 409)

# ── 3. CLI commands ────────────────────────────────────────────────────────────
print("\n[3] CLI commands")

# All 18 real test definitions have profile "dev" (settings.default_profile).
# Create a matching ConnectionProfile so trigger_run can find enabled tests.
r = requests.post(f"{API_URL}/api/v1/profiles", json={
    "name": "dev",
    "connection_url": "sqlite:///./smoke_dev.db",
    "db_type": "sqlite",
}, headers=HEADERS)
run_profile_id = r.json().get("id") if r.status_code == 201 else None
# 409 = "dev" already exists — fine, don't delete it at cleanup.

tmpdir = tempfile.mkdtemp(prefix="aegis_smoke_")

try:
    # aegis init
    result = cli("init", cwd=tmpdir)
    check("aegis init exits 0", result.returncode == 0, result.stderr)
    check(
        "aegis/config.yaml created",
        (Path(tmpdir) / "aegis" / "config.yaml").exists(),
    )

    # Point config at localhost with the "dev" profile
    (Path(tmpdir) / "aegis" / "config.yaml").write_text(
        f"api_url: {API_URL}\ndefault_profile: dev\n"
    )

    # Pull real definitions first — replaces the init template so push is net-zero
    result = cli("pull", cwd=tmpdir)
    check("aegis pull exits 0", result.returncode == 0, result.stderr)

    # aegis push — syncs pulled content back (no net change, confirms round-trip)
    result = cli("push", cwd=tmpdir)
    check("aegis push exits 0", result.returncode == 0, result.stderr)
    check(
        "push reports counts",
        any(k in result.stdout for k in ("created=", "updated=", "unchanged=")),
        result.stdout,
    )

    # aegis run --no-wait (trigger only — run may fail in background if tables absent)
    result = cli("run", "--no-wait", cwd=tmpdir)
    check("aegis run --no-wait exits 0", result.returncode == 0, result.stderr)
    check("run shows run ID", "Run #" in result.stdout, result.stdout)

    # aegis status
    result = cli("status", cwd=tmpdir)
    check("aegis status exits 0", result.returncode == 0, result.stderr)
    check(
        "status shows a run row",
        any(s in result.stdout for s in ("QUEUED", "RUNNING", "COMPLETE", "FAILED")),
        result.stdout,
    )

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# ── 4. Cleanup ─────────────────────────────────────────────────────────────────
print("\n[4] Cleanup")
if profile_id:
    r = requests.delete(f"{API_URL}/api/v1/profiles/{profile_id}", headers=HEADERS)
    check("DELETE smoke-test profile → 204", r.status_code == 204)
if run_profile_id:
    r = requests.delete(f"{API_URL}/api/v1/profiles/{run_profile_id}", headers=HEADERS)
    check("DELETE dev smoke profile → 204", r.status_code == 204)

# ── Result ─────────────────────────────────────────────────────────────────────
print()
if _failed:
    print(f"── {len(_failed)} check(s) FAILED: {', '.join(_failed)}")
    sys.exit(1)
else:
    print("── All checks passed ──────────────────────────────────────\n")
