import os
import sys
from dotenv import load_dotenv

# The hosted Aegis API URL is fixed — every client talks to the same endpoint, so it is
# never a client-facing setting. AEGIS_API_URL exists only as an internal override for
# Aegis-side development (e.g. pointing the CLI at a local server).
DEFAULT_API_URL = "https://api.aegis-dq.com"


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
