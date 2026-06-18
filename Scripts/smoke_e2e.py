#!/usr/bin/env python3
"""
E2E smoke test (file-driven profiles model).

Requirements:
  - Stack running: make start
  - .env has COMET_API_KEY
  - comet CLI installed: pip install -e ".[dev]"

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
API_KEY = os.getenv("COMET_API_KEY") or os.getenv("DQF_API_KEY")

if not API_KEY:
    print("COMET_API_KEY not set in .env — aborting")
    sys.exit(1)

HEADERS = {"X-Api-Key": API_KEY}
PASS = "OK"
FAIL = "XX"
_failed = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  {PASS} {label}")
    else:
        msg = f"  {FAIL} {label}" + (f"  ({detail})" if detail else "")
        print(msg)
        _failed.append(label)


def cli(*args, cwd=None) -> subprocess.CompletedProcess:
    env = {**os.environ, "COMET_API_KEY": API_KEY}
    return subprocess.run(
        ["comet", *args], capture_output=True, text=True, cwd=cwd, env=env
    )


print("\n-- E2E Smoke Test --------------------------------------------")

# -- 1. API health --------------------------------------------------------------
print("\n[1] API health")
try:
    r = requests.get(f"{API_URL}/api/v1/health", timeout=5)
    check("GET /api/v1/health -> 200", r.status_code == 200, r.text)
except requests.ConnectionError:
    print(f"  {FAIL} Cannot reach {API_URL} — is 'make start' running?")
    sys.exit(1)

# -- 2. Connection profiles (file-driven /sync) ---------------------------------
print("\n[2] Connection profiles — /profiles/sync")

# Upload a connection YAML; the dashboard stores it per-client and prefers it
# over the on-disk file. The "dev" profile matches the test_definitions template
# (settings.default_profile), so a subsequent run can find enabled tests.
_SMOKE_CONN_YAML = (
    "dev:\n"
    "  type: sqlite\n"
    "  path: ../../data/raw/sample_ecommerce.db\n"
)
r = requests.post(
    f"{API_URL}/api/v1/profiles/sync",
    json={"yaml_content": _SMOKE_CONN_YAML},
    headers=HEADERS,
)
check("POST /api/v1/profiles/sync -> 200", r.status_code == 200, r.text)
synced = r.json().get("profiles", []) if r.status_code == 200 else []
check("sync reports the 'dev' profile", "dev" in synced, str(synced))

# GET must now return the synced profile names (no secrets, no CRUD).
r = requests.get(f"{API_URL}/api/v1/profiles", headers=HEADERS)
body = r.json() if r.status_code == 200 else []
check("GET /api/v1/profiles includes dev", any(p["name"] == "dev" for p in body))
check(
    "profiles expose names only (no secrets)",
    all(set(p.keys()) <= {"name", "is_default"} for p in body),
    str(body),
)

# -- 3. CLI commands ------------------------------------------------------------
print("\n[3] CLI commands")

tmpdir = tempfile.mkdtemp(prefix="comet_smoke_")

try:
    # comet init — scaffolds comet/{config,test_definitions,database_connection}.yaml
    result = cli("init", cwd=tmpdir)
    check("comet init exits 0", result.returncode == 0, result.stderr)
    check(
        "comet/config.yaml created",
        (Path(tmpdir) / "comet" / "config.yaml").exists(),
    )

    # Point config at localhost with the "dev" profile
    (Path(tmpdir) / "comet" / "config.yaml").write_text(
        f"api_url: {API_URL}\ndefault_profile: dev\n"
    )

    # Pull real definitions first — replaces the init template so push is net-zero
    result = cli("pull", cwd=tmpdir)
    check("comet pull exits 0", result.returncode == 0, result.stderr)

    # comet push — syncs test_definitions.yaml AND database_connection.yaml
    result = cli("push", cwd=tmpdir)
    check("comet push exits 0", result.returncode == 0, result.stderr)
    check(
        "push reports test counts",
        any(k in result.stdout for k in ("created=", "updated=", "unchanged=")),
        result.stdout,
    )
    check(
        "push syncs connection profiles",
        "Profiles synced" in result.stdout,
        result.stdout,
    )

    # comet run --no-wait (trigger only — run may fail in background if tables absent)
    result = cli("run", "--no-wait", cwd=tmpdir)
    check("comet run --no-wait exits 0", result.returncode == 0, result.stderr)
    check("run shows run ID", "Run #" in result.stdout, result.stdout)

    # comet status
    result = cli("status", cwd=tmpdir)
    check("comet status exits 0", result.returncode == 0, result.stderr)
    check(
        "status shows a run row",
        any(s in result.stdout for s in ("QUEUED", "RUNNING", "COMPLETE", "FAILED")),
        result.stdout,
    )

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# -- Result ---------------------------------------------------------------------
print()
if _failed:
    print(f"-- {len(_failed)} check(s) FAILED: {', '.join(_failed)}")
    sys.exit(1)
else:
    print("-- All checks passed ---------------------------------------\n")
