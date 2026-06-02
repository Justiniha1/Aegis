from cli.profiles_sync import (
    default_secret_env, parse_yaml_profile, profile_to_payload, env_ref_or_none,
)


def test_default_secret_env():
    assert default_secret_env("staging") == "AEGIS_STAGING_PASSWORD"
    assert default_secret_env("prod-mysql") == "AEGIS_PROD_MYSQL_PASSWORD"


def test_env_ref_extracts_var_name():
    assert env_ref_or_none("${STAGING_DB_PASSWORD}") == "STAGING_DB_PASSWORD"
    assert env_ref_or_none("literalpw") is None
    assert env_ref_or_none(None) is None


def test_parse_postgres_profile_uses_yaml_env_ref():
    p = parse_yaml_profile("staging", {
        "type": "postgres", "host": "h", "port": 5432, "database": "db",
        "username": "u", "password": "${STAGING_DB_PASSWORD}",
    })
    assert p["db_type"] == "postgresql"
    assert p["host"] == "h" and p["port"] == 5432 and p["database"] == "db"
    assert p["secret_env"] == "STAGING_DB_PASSWORD"


def test_parse_postgres_literal_password_defaults_env_name():
    p = parse_yaml_profile("staging", {"type": "postgres", "host": "h", "username": "u", "password": "raw"})
    assert p["secret_env"] == "AEGIS_STAGING_PASSWORD"
    assert p["_literal_secret"] == "raw"     # carried so push can send it


def test_parse_sqlite_has_no_secret():
    p = parse_yaml_profile("dev", {"type": "sqlite", "path": "/app/data/x.db"})
    assert p["db_type"] == "sqlite" and p["sqlite_path"] == "/app/data/x.db"
    assert p["secret_env"] is None


def test_profile_to_payload_resolves_env(monkeypatch):
    monkeypatch.setenv("STAGING_DB_PASSWORD", "fromenv")
    p = parse_yaml_profile("staging", {"type": "postgres", "host": "h", "username": "u",
                                       "password": "${STAGING_DB_PASSWORD}"})
    payload, warn = profile_to_payload("staging", p)
    assert payload["secret_value"] == "fromenv"
    assert payload["secret_env"] == "STAGING_DB_PASSWORD"
    assert warn is None


def test_profile_to_payload_unset_env_omits_secret_and_warns(monkeypatch):
    monkeypatch.delenv("STAGING_DB_PASSWORD", raising=False)
    p = parse_yaml_profile("staging", {"type": "postgres", "host": "h", "username": "u",
                                       "password": "${STAGING_DB_PASSWORD}"})
    payload, warn = profile_to_payload("staging", p)
    assert "secret_value" not in payload          # no-clobber: don't send a secret we don't have
    assert "STAGING_DB_PASSWORD" in warn
