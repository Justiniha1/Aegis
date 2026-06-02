from cli.commands.push import _reconcile_profiles


class FakeClient:
    """Records calls; serves a mutable list of remote profiles."""
    def __init__(self, remote):
        self.remote = remote                  # list[dict] with id,name
        self.posts, self.puts, self.deletes = [], [], []

    def get(self, path):
        assert path == "/api/v1/profiles"
        return self.remote

    def post(self, path, json):
        self.posts.append(json)
        return {"id": 999, **json}

    def put(self, path, json):
        self.puts.append((path, json))
        return {"id": int(path.rsplit("/", 1)[1]), **json}

    def delete(self, path):
        self.deletes.append(path)


def test_push_creates_updates_deletes(monkeypatch):
    monkeypatch.setenv("AEGIS_STAGING_PASSWORD", "pw")
    local = {
        "dev": {"type": "sqlite", "path": "/app/data/x.db"},
        "staging": {"type": "postgres", "host": "h", "username": "u",
                    "password": "${AEGIS_STAGING_PASSWORD}"},
    }
    remote = [
        {"id": 1, "name": "staging", "db_type": "postgresql", "host": "old"},
        {"id": 2, "name": "obsolete", "db_type": "postgresql"},
    ]
    c = FakeClient(remote)
    summary = _reconcile_profiles(c, local, confirm=lambda *_a, **_k: True)
    names_posted = {p["name"] for p in c.posts}
    assert "dev" in names_posted and "staging" in names_posted
    assert c.deletes == ["/api/v1/profiles/2"]      # obsolete removed
    assert summary["deleted"] == 1


def test_push_unset_env_warns_and_omits_secret(monkeypatch, capsys):
    monkeypatch.delenv("AEGIS_STAGING_PASSWORD", raising=False)
    local = {"staging": {"type": "postgres", "host": "h", "username": "u",
                         "password": "${AEGIS_STAGING_PASSWORD}"}}
    c = FakeClient([])
    _reconcile_profiles(c, local, confirm=lambda *_a, **_k: True)
    assert "secret_value" not in c.posts[0]
    assert "not set" in capsys.readouterr().out
