import sys

import pytest

from connector.duckdb_adapter import DuckDBConnector
from mcp_server.backends import build_connector


def test_duckdb_backend_returns_duckdb_connector(tmp_path):
    db_path = tmp_path / "warehouse.duckdb"

    connector = build_connector("duckdb", db_path=str(db_path))

    assert isinstance(connector, DuckDBConnector)
    connector.close()


def test_unknown_backend_raises_value_error_listing_options(tmp_path):
    with pytest.raises(ValueError, match="duckdb.*snowflake.*databricks"):
        build_connector("bigquery", db_path=str(tmp_path / "warehouse.duckdb"))


def test_databricks_backend_raises_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError):
        build_connector("databricks", db_path=str(tmp_path / "warehouse.duckdb"))


def test_snowflake_backend_without_extra_raises_helpful_runtime_error(tmp_path, monkeypatch):
    # Simulate the extra not being installed regardless of what's actually
    # in this dev environment's venv, by forcing the lazy import to fail.
    monkeypatch.setitem(sys.modules, "connector.snowflake_adapter", None)
    monkeypatch.setitem(sys.modules, "snowflake.connector", None)
    monkeypatch.setitem(sys.modules, "snowflake", None)

    with pytest.raises(RuntimeError, match="uv sync --extra snowflake"):
        build_connector("snowflake", db_path=str(tmp_path / "warehouse.duckdb"))


def test_snowflake_backend_returns_snowflake_connector(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_USER", "test-user")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "test-password")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "test-warehouse")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "test-database")
    monkeypatch.setattr("snowflake.connector.connect", lambda **kwargs: object())

    from connector.snowflake_adapter import SnowflakeConnector

    connector = build_connector("snowflake", db_path="unused")

    assert isinstance(connector, SnowflakeConnector)
