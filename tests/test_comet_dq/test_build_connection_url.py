"""Unit tests for backend.core.database_connector.build_connection_url.

Tests cover: Snowflake URL construction, ${ENV} loud-fail, credential scrubbing,
and regression guards for the existing MySQL and MSSQL branches.
"""
import pytest

from backend.core.database_connector import build_connection_url


# ---------------------------------------------------------------------------
# Snowflake URL construction
# ---------------------------------------------------------------------------

def test_snowflake_url_basic():
    profile = {
        "type": "snowflake",
        "account": "myorg-myacct",
        "username": "u",
        "password": "p",
        "database": "DB",
        "warehouse": "WH",
        "role": "R",
    }
    url = build_connection_url(profile)
    assert url.startswith("snowflake://u:p@myorg-myacct/DB")
    assert "warehouse=WH" in url
    assert "role=R" in url


def test_snowflake_url_omits_empty_warehouse_role():
    profile = {
        "type": "snowflake",
        "account": "myorg-myacct",
        "username": "u",
        "password": "p",
        "database": "DB",
    }
    url = build_connection_url(profile)
    assert "warehouse=" not in url
    assert "role=" not in url
    # No dangling ? or &
    assert not url.endswith("?")
    assert not url.endswith("&")


def test_snowflake_account_no_domain_suffix():
    profile = {
        "type": "snowflake",
        "account": "myorg-myacct.snowflakecomputing.com",
        "username": "u",
        "password": "p",
        "database": "DB",
    }
    url = build_connection_url(profile)
    assert "snowflakecomputing.com" not in url
    assert "myorg-myacct" in url


# ---------------------------------------------------------------------------
# Regression guards for existing branches
# ---------------------------------------------------------------------------

def test_mysql_url_unchanged():
    profile = {
        "type": "mysql",
        "username": "u",
        "password": "p",
        "host": "h",
        "database": "db",
    }
    url = build_connection_url(profile)
    assert url == "mysql+pymysql://u:p@h:3306/db"


def test_mssql_url_unchanged():
    profile = {
        "type": "mssql",
        "username": "u",
        "password": "p",
        "host": "h",
        "database": "db",
    }
    url = build_connection_url(profile)
    assert url.startswith("mssql+pyodbc://")
    assert "driver=ODBC+Driver+17+for+SQL+Server" in url


# ---------------------------------------------------------------------------
# Loud-fail on unset ${ENV} vars
# ---------------------------------------------------------------------------

def test_unset_env_var_raises_named():
    profile = {
        "type": "snowflake",
        "account": "myorg-myacct",
        "username": "u",
        "password": "${SNOWFLAKE_PASSWORD}",
        "database": "DB",
    }
    with pytest.raises(ValueError) as exc_info:
        build_connection_url(profile)
    msg = str(exc_info.value)
    assert "SNOWFLAKE_PASSWORD" in msg
    assert "not set" in msg
    assert "${" not in msg


# ---------------------------------------------------------------------------
# Credential scrubbing in error messages
# ---------------------------------------------------------------------------

def test_error_never_contains_credentials():
    profile = {
        "type": "unsupportedtype",
        "username": "u",
        "password": "supersecret",
        "host": "h",
        "database": "db",
    }
    with pytest.raises(ValueError) as exc_info:
        build_connection_url(profile)
    assert "supersecret" not in str(exc_info.value)
