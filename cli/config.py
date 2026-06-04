import os
import sys
from dotenv import load_dotenv

from aegis_dq._client import DEFAULT_API_URL

# api_url is fixed and shared with the SDK (single source of truth: aegis_dq._client).
# AEGIS_API_URL exists only as an internal override for Aegis-side development.


def load_config() -> dict:
    """Build CLI config purely from the environment — there is no config file.

    A client needs only AEGIS_API_KEY plus their database_connection.yaml. The API URL is
    fixed (hosted); the default profile is "dev" unless a command passes --profile.
    AEGIS_API_URL exists only as an internal override for Aegis-side development.
    """
    load_dotenv()

    api_key = os.environ.get("AEGIS_API_KEY")
    if not api_key:
        print("[aegis] AEGIS_API_KEY not set. Add it to your .env file: AEGIS_API_KEY=your-key")
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_url": os.environ.get("AEGIS_API_URL", DEFAULT_API_URL),
        "default_profile": "dev",
    }
