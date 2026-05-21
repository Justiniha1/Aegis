import os
import sys
from pathlib import Path

# Make project root importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from backend.core.config_loader import load_config, load_config_from_api, CONFIG_DIR
from backend.core.result_handler import send_to_dashboard
from backend.core.test_engine import TestEngine

_API_URL = os.getenv("DQF_API_URL", "").rstrip("/")
_API_KEY = os.getenv("DQF_API_KEY", "")


def _sync_yaml_to_api():
    """Push local YAML test definitions to the API so manual edits are reflected in the DB."""
    yaml_path = CONFIG_DIR / "test_definitions.yaml"
    if not yaml_path.exists():
        return

    try:
        yaml_content = yaml_path.read_text(encoding="utf-8")
        resp = requests.post(
            f"{_API_URL}/api/v1/tests/sync",
            json={"yaml_content": yaml_content},
            headers={"X-API-Key": _API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            changes = data.get("created", 0) + data.get("updated", 0) + data.get("deleted", 0)
            if changes > 0:
                print(f"[sync] YAML → DB: {data['created']} created, {data['updated']} updated, {data['deleted']} deleted")
            else:
                print("[sync] YAML and DB are in sync")
        else:
            print(f"[warn] YAML sync failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[warn] Could not sync YAML to API: {e}")


def main():
    if _API_URL and _API_KEY:
        # Step 1: Sync local YAML edits to the database
        _sync_yaml_to_api()

        # Step 2: Load config from API (which now includes any YAML changes)
        yaml_config = load_config()   # still need connections from YAML
        try:
            config = load_config_from_api(_API_URL, _API_KEY, yaml_config.connections)
            print("[info] Test definitions loaded from Dashboard API\n")
        except RuntimeError as e:
            print(f"[warn] {e} — falling back to local YAML\n")
            config = yaml_config
    else:
        config = load_config()

    engine = TestEngine(config)
    results = engine.run()
    engine.print_summary(results)
    saved_path = engine.save_results(results)
    send_to_dashboard(results, run_timestamp=saved_path.stem.replace("test_results_", ""), profile=config.engine.default_profile)


if __name__ == "__main__":
    main()
