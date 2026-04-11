import os
import sys
from pathlib import Path

# Make project root importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.config_loader import load_config, load_config_from_api
from backend.core.result_handler import send_to_dashboard
from backend.core.test_engine import TestEngine

_API_URL = os.getenv("DQF_API_URL", "").rstrip("/")
_API_KEY = os.getenv("DQF_API_KEY", "")


def main():
    # If API is configured, fetch test definitions from it.
    # Otherwise fall back to local YAML files.
    if _API_URL and _API_KEY:
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
    send_to_dashboard(results, run_timestamp=saved_path.stem.replace("test_results_", ""))


if __name__ == "__main__":
    main()
