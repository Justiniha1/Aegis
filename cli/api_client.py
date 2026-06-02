import requests


class AegisClient:
    def __init__(self, api_url: str, api_key: str):
        self._base = api_url.rstrip("/")
        self._headers = {"X-Api-Key": api_key}

    def get(self, path: str, **kwargs) -> dict:
        resp = requests.get(f"{self._base}{path}", headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict = None, **kwargs) -> dict:
        resp = requests.post(f"{self._base}{path}", json=json, headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, path: str, **kwargs) -> str:
        resp = requests.get(f"{self._base}{path}", headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.text

