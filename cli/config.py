import os
import sys
from dotenv import load_dotenv, find_dotenv

from comet_dq._client import DEFAULT_API_URL

# The hosted API URL is fixed and baked into the SDK (single source of truth:
# comet_dq._client.DEFAULT_API_URL). It is intentionally NOT configurable — not via a
# config file and not via any environment variable — so a client only ever sets COMET_API_KEY.


def load_config() -> dict:
    """Build CLI config purely from the environment — there is no config file.

    The only client-settable value is COMET_API_KEY (via env or a .env file). The API URL is
    always the hosted default; the default profile is "dev" unless a command passes --profile.
    """
    # Resolve .env from the user's current directory (walking up), NOT from this
    # module's install location. Without usecwd=True, python-dotenv searches up from
    # cli/config.py — which lands in site-packages for a real `pip install` and never
    # finds the client's project .env. usecwd=True makes the .env live where the user
    # actually runs comet (next to their comet/ config), matching the YAML resolution.
    load_dotenv(find_dotenv(usecwd=True))

    api_key = os.environ.get("COMET_API_KEY")
    if not api_key:
        print("[comet] COMET_API_KEY not set. Add it to your .env file: COMET_API_KEY=your-key")
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_url": DEFAULT_API_URL,
        "default_profile": "dev",
    }
