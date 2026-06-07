import os
import sys
from dotenv import load_dotenv

from aegis_dq._client import DEFAULT_API_URL

# The hosted API URL is fixed and baked into the SDK (single source of truth:
# aegis_dq._client.DEFAULT_API_URL). It is intentionally NOT configurable — not via a
# config file and not via any environment variable — so a client only ever sets AEGIS_API_KEY.


def load_config() -> dict:
    """Build CLI config purely from the environment — there is no config file.

    The only client-settable value is AEGIS_API_KEY (via env or a .env file). The API URL is
    always the hosted default; the default profile is "dev" unless a command passes --profile.
    """
    load_dotenv()

    api_key = os.environ.get("AEGIS_API_KEY")
    if not api_key:
        print("[aegis] AEGIS_API_KEY not set. Add it to your .env file: AEGIS_API_KEY=your-key")
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_url": DEFAULT_API_URL,
        "default_profile": "dev",
    }
