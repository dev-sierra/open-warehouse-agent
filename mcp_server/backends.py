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

    "duckdb" is always available. "snowflake" imports
    connector.snowflake_adapter lazily, so the optional `snowflake` extra
    only needs to be installed when this backend is actually selected — a
    missing extra is caught and re-raised with the `uv sync --extra
    snowflake` fix. "databricks" has no adapter yet (see README roadmap).
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
        raise NotImplementedError(
            "the databricks backend has no adapter yet — see README roadmap"
        )

    raise ValueError(
        f"unknown backend {backend!r} — supported backends: {', '.join(SUPPORTED_BACKENDS)}"
    )
