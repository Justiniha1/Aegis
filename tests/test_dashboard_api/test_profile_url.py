import pytest
from types import SimpleNamespace
from dashboard_api.profile_url import build_connection_url


def _profile(**kw):
    base = dict(db_type="postgresql", host="db.example.com", port=5432,
                database="analytics", username="reader", sqlite_path=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_postgres_url_with_secret():
    url = build_connection_url(_profile(), "p@ss/word")
    assert url == "postgresql://reader:p%40ss%2Fword@db.example.com:5432/analytics"


def test_mysql_uses_pymysql_driver():
    url = build_connection_url(_profile(db_type="mysql", port=3306), "pw")
    assert url == "mysql+pymysql://reader:pw@db.example.com:3306/analytics"


def test_sqlite_uses_path_and_ignores_secret():
    p = _profile(db_type="sqlite", host=None, port=None, database=None,
                 username=None, sqlite_path="/app/data/sample.db")
    assert build_connection_url(p, None) == "sqlite:////app/data/sample.db"


def test_missing_secret_for_password_db_raises():
    with pytest.raises(ValueError, match="requires a secret"):
        build_connection_url(_profile(), None)
