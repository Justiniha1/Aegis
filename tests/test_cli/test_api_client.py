"""Tests for the CLI HTTP client error translation (H11).

The CLI used to surface raw requests exceptions (e.g. "401 Client Error: Unauthorized
for url: https://...") straight to users. CometClient must instead raise CometAPIError
with an actionable, URL-free message, while success paths are unchanged.
"""

import pytest
import requests

from cli.api_client import CometClient, CometAPIError


@pytest.fixture
def client():
    return CometClient(api_url="https://api.example.com", api_key="k")


def test_get_success_returns_json(client, requests_mock):
    requests_mock.get("https://api.example.com/x", json={"ok": True})
    assert client.get("/x") == {"ok": True}


def test_post_success_returns_json(client, requests_mock):
    requests_mock.post("https://api.example.com/x", json={"run_id": 7})
    assert client.post("/x", json={"a": 1}) == {"run_id": 7}


def test_get_text_success_returns_text(client, requests_mock):
    requests_mock.get("https://api.example.com/x", text="tests:\n- name: a\n")
    assert client.get_text("/x") == "tests:\n- name: a\n"


def test_401_raises_friendly_error(client, requests_mock):
    requests_mock.get("https://api.example.com/x", status_code=401, json={"detail": "Invalid API key"})
    with pytest.raises(CometAPIError) as ei:
        client.get("/x")
    msg = str(ei.value)
    assert "COMET_API_KEY" in msg
    assert "Client Error" not in msg
    assert "https://" not in msg


def test_422_includes_server_detail(client, requests_mock):
    requests_mock.post(
        "https://api.example.com/api/v1/profiles/sync",
        status_code=422,
        json={"detail": "Profile 'prod' has a literal 'password'."},
    )
    with pytest.raises(CometAPIError) as ei:
        client.post("/api/v1/profiles/sync", json={"yaml_content": "..."})
    assert "literal 'password'" in str(ei.value)


def test_500_raises_friendly_error(client, requests_mock):
    requests_mock.get("https://api.example.com/x", status_code=503)
    with pytest.raises(CometAPIError) as ei:
        client.get("/x")
    assert "503" in str(ei.value)
    assert "Client Error" not in str(ei.value)


def test_connection_error_is_friendly(client, requests_mock):
    requests_mock.get("https://api.example.com/x", exc=requests.exceptions.ConnectionError)
    with pytest.raises(CometAPIError) as ei:
        client.get("/x")
    assert "Could not reach" in str(ei.value)
