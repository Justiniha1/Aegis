import os
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv


def load_config() -> dict:
    load_dotenv()

    config_path = Path("aegis") / "config.yaml"
    if not config_path.exists():
        print("[aegis] aegis/config.yaml not found. Run 'aegis init' to set up your project.")
        sys.exit(1)

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    api_key = os.environ.get("AEGIS_API_KEY")
    if not api_key:
        print("[aegis] AEGIS_API_KEY not set. Add it to your .env file: AEGIS_API_KEY=your-key")
        sys.exit(1)

    cfg["api_key"] = api_key
    cfg.setdefault("api_url", "https://api.aegis-dq.com")
    cfg.setdefault("default_profile", "dev")
    return cfg
