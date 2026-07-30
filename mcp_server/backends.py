"""Backend selection: turns a WAREHOUSE_BACKEND name into a connector.

Kept separate from mcp_server/__main__.py so the dispatch logic is
importable and testable without going through the module's __main__ guard.
"""

from __future__ import annotations

from connector.duckdb_adapter import DuckDBConnector
from connector.protocol import WarehouseConnector

SUPPORTED_BACKENDS = ("duckdb", "snowflake", "databricks")


def build_connector(backend: str, *, db_path: str) -> WarehouseConnector:
    """Construct the connector for one backend name.

    "duckdb" is always available. "snowflake" and "databricks" import
    their adapters lazily, so the optional extra only needs to be
    installed when that backend is actually selected -- a missing extra
    is caught and re-raised with the relevant `uv sync --extra ...` fix.
    """
    if backend == "duckdb":
        return DuckDBConnector(db_path)

    if backend == "snowflake":
        try:
            from connector.snowflake_adapter import SnowflakeConnector
        except ImportError as e:
            raise RuntimeError(
                "the snowflake backend requires the optional `snowflake` "
                "extra — run `uv sync --extra snowflake` and set "
                "SNOWFLAKE_ACCOUNT/USER/PASSWORD/WAREHOUSE/DATABASE"
            ) from e
        return SnowflakeConnector()

    if backend == "databricks":
        try:
            from connector.databricks_adapter import DatabricksConnector
        except ImportError as e:
            raise RuntimeError(
                "the databricks backend requires the optional `databricks` "
                "extra — run `uv sync --extra databricks` and set "
                "DATABRICKS_SERVER_HOSTNAME/HTTP_PATH/CATALOG plus either "
                "CLIENT_ID+CLIENT_SECRET or TOKEN"
            ) from e
        return DatabricksConnector()

    raise ValueError(
        f"unknown backend {backend!r} — supported backends: {', '.join(SUPPORTED_BACKENDS)}"
    )
