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


def test_snowflake_backend_without_extra_raises_helpful_runtime_error(tmp_path):
    # This dev environment doesn't have the optional `snowflake` extra
    # installed, so this exercises the real ImportError fallback rather
    # than needing to mock it.
    with pytest.raises(RuntimeError, match="uv sync --extra snowflake"):
        build_connector("snowflake", db_path=str(tmp_path / "warehouse.duckdb"))
