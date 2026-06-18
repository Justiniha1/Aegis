import requests

_TIMEOUT = 15  # seconds per request


class CometAPIError(Exception):
    """A user-facing error from an Comet API call.

    Carries an actionable, URL-free message so the CLI can print it directly instead
    of leaking raw requests exceptions like "401 Client Error: ... for url: https://...".
    """


class CometClient:
    def __init__(self, api_url: str, api_key: str):
        self._base = api_url.rstrip("/")
        self._headers = {"X-Api-Key": api_key}

    def get(self, path: str, **kwargs) -> dict:
        return self._request("GET", path, **kwargs).json()

    def post(self, path: str, json: dict = None, **kwargs) -> dict:
        return self._request("POST", path, json=json, **kwargs).json()

    def get_text(self, path: str, **kwargs) -> str:
        return self._request("GET", path, **kwargs).text

    # ── internals ────────────────────────────────────────────────────────────
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self._base}{path}"
        try:
            resp = requests.request(method, url, headers=self._headers, timeout=_TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            raise CometAPIError(self._explain_http_error(e.response, path)) from e
        except requests.exceptions.ConnectionError as e:
            raise CometAPIError(
                f"Could not reach the Comet API at {self._base}. "
                "Check your connection and that the service is running."
            ) from e
        except requests.exceptions.Timeout as e:
            raise CometAPIError(
                f"The Comet API at {self._base} did not respond in time. Try again shortly."
            ) from e

    @staticmethod
    def _explain_http_error(resp: requests.Response, path: str) -> str:
        code = resp.status_code
        detail = None
        try:
            body = resp.json()
            if isinstance(body, dict):
                detail = body.get("detail")
        except ValueError:
            detail = None

        if code in (401, 403):
            return (
                "Authentication failed — check your COMET_API_KEY "
                "(find it in the dashboard Settings)."
            )
        if code == 404:
            return f"Not found ({path}). The resource may not exist or the API URL is wrong."
        if 400 <= code < 500:
            return f"Request rejected (HTTP {code}): {detail or resp.reason}"
        return f"Comet API error (HTTP {code}). Try again shortly."
