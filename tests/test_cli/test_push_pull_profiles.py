from cli.commands.push import _reconcile_profiles
from cli.commands.pull import _profiles_to_yaml_dict, _readiness_lines


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


def test_profiles_to_yaml_dict_uses_env_ref_placeholder():
    remote = [
        {"name": "dev", "db_type": "sqlite", "sqlite_path": "/app/data/x.db", "secret_env": None,
         "host": None, "port": None, "database": None, "username": None},
        {"name": "staging", "db_type": "postgresql", "host": "h", "port": 5432, "database": "db",
         "username": "u", "secret_env": "AEGIS_STAGING_PASSWORD", "sqlite_path": None},
    ]
    d = _profiles_to_yaml_dict(remote)
    assert d["dev"] == {"type": "sqlite", "path": "/app/data/x.db"}
    assert d["staging"]["password"] == "${AEGIS_STAGING_PASSWORD}"
    assert d["staging"]["type"] == "postgresql" and d["staging"]["host"] == "h"


def test_readiness_lines_flags_unset(monkeypatch):
    monkeypatch.delenv("AEGIS_STAGING_PASSWORD", raising=False)
    remote = [{"name": "staging", "db_type": "postgresql", "secret_env": "AEGIS_STAGING_PASSWORD"},
              {"name": "dev", "db_type": "sqlite", "secret_env": None}]
    lines = _readiness_lines(remote)
    joined = "\n".join(lines)
    assert "AEGIS_STAGING_PASSWORD" in joined and "NOT SET" in joined
    assert "no secret needed" in joined
