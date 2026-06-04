"""Load (or reset) the Airflow demo dataset into a Postgres database.

Usage (PowerShell):
    $env:DEMO_DATABASE_URL = "<demo-db PUBLIC connection URL>"
    python deploy/demo/db/load_seed.py

The URL must be the PUBLIC Railway URL (host ends in something like
`.proxy.rlwy.net`), not the internal `*.railway.internal` host, because this runs
from your laptop. Re-running this resets the demo to a known-good state.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SEED = Path(__file__).with_name("seed_demo.sql")


def main() -> int:
    url = os.environ.get("DEMO_DATABASE_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not url:
        print("ERROR: set DEMO_DATABASE_URL (or pass the URL as the first argument).")
        return 2

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run:  pip install psycopg2-binary")
        return 2

    sql = SEED.read_text(encoding="utf-8")
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("SELECT COUNT(*) FROM customers;")
            customers = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM orders;")
            orders = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"OK: loaded demo data -> customers={customers}, orders={orders}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
