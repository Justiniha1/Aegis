"""Tests for production-config guardrails.

In production (COMET_ENV=production) the API must refuse to run with an insecure JWT
secret or a non-persistent (SQLite/unset) database, since either silently loses or
compromises client data on Railway. In development the checks are inert.
"""

from dashboard_api.runtime_checks import check_production_config

_GOOD = {
    "COMET_ENV": "production",
    "JWT_SECRET_KEY": "a" * 64,
    "DATABASE_URL": "postgresql://u:p@host:5432/db",
    "COMET_ADMIN_TOKEN": "admin-secret",
}


def test_dev_environment_has_no_problems():
    # Default (no COMET_ENV) is development — guardrails are inert.
    assert check_production_config({}) == []
    assert check_production_config({"COMET_ENV": "development"}) == []


def test_production_with_good_config_passes():
    assert check_production_config(_GOOD) == []


def test_production_flags_placeholder_jwt_secret():
    for bad in ("", "change-me-in-production"):
        env = {**_GOOD, "JWT_SECRET_KEY": bad}
        problems = check_production_config(env)
        assert any("JWT_SECRET_KEY" in p for p in problems)


def test_production_flags_missing_jwt_secret():
    env = {k: v for k, v in _GOOD.items() if k != "JWT_SECRET_KEY"}
    problems = check_production_config(env)
    assert any("JWT_SECRET_KEY" in p for p in problems)


def test_production_flags_sqlite_database():
    env = {**_GOOD, "DATABASE_URL": "sqlite:///./dashboard.db"}
    problems = check_production_config(env)
    assert any("DATABASE_URL" in p for p in problems)


def test_production_flags_missing_database_url():
    env = {k: v for k, v in _GOOD.items() if k != "DATABASE_URL"}
    problems = check_production_config(env)
    assert any("DATABASE_URL" in p for p in problems)


def test_production_flags_missing_admin_token():
    env = {k: v for k, v in _GOOD.items() if k != "COMET_ADMIN_TOKEN"}
    problems = check_production_config(env)
    assert any("COMET_ADMIN_TOKEN" in p for p in problems)


def test_production_collects_multiple_problems():
    env = {"COMET_ENV": "production"}  # JWT, DB and admin token all unset
    problems = check_production_config(env)
    assert len(problems) == 3


def test_comet_env_is_case_insensitive():
    env = {**_GOOD, "COMET_ENV": "Production", "JWT_SECRET_KEY": ""}
    assert any("JWT_SECRET_KEY" in p for p in check_production_config(env))
