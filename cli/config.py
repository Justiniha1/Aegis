import os
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv

# The hosted Aegis API URL is fixed — every client talks to the same endpoint, so it is
# never a client-facing setting. AEGIS_API_URL exists only as an internal override for
# Aegis-side development (e.g. pointing the CLI at a local server); it is intentionally
# NOT configurable via aegis/config.yaml.
DEFAULT_API_URL = "https://api.aegis-dq.com"


def load_config() -> dict:
    load_dotenv()

    config_path = Path("aegis") / "config.yaml"
    cfg = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}

    api_key = os.environ.get("AEGIS_API_KEY")
    if not api_key:
        print("[aegis] AEGIS_API_KEY not set. Add it to your .env file: AEGIS_API_KEY=your-key")
        sys.exit(1)

    cfg["api_key"] = api_key
    # api_url is fixed: any value in config.yaml is ignored. Only the internal
    # AEGIS_API_URL env override is honored, so clients never need to set it.
    cfg["api_url"] = os.environ.get("AEGIS_API_URL", DEFAULT_API_URL)
    cfg.setdefault("default_profile", "dev")
    return cfg
