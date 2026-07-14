"""Entry point: uv run python -m mcp_server

Runs the MCP server over stdio against a local DuckDB file — the
zero-cloud-account path. Override WAREHOUSE_DB_PATH / WAREHOUSE_AUDIT_PATH
to point elsewhere.
"""

from __future__ import annotations

import os

from connector.duckdb_adapter import DuckDBConnector
from mcp_server.audit import AuditLog
from mcp_server.server import build_server

DEFAULT_DB_PATH = "data/warehouse.duckdb"
DEFAULT_AUDIT_PATH = "data/audit.jsonl"


def main() -> None:
    db_path = os.environ.get("WAREHOUSE_DB_PATH", DEFAULT_DB_PATH)
    audit_path = os.environ.get("WAREHOUSE_AUDIT_PATH", DEFAULT_AUDIT_PATH)

    connector = DuckDBConnector(db_path)
    audit_log = AuditLog(audit_path)
    server = build_server(connector, audit_log)
    server.run()


if __name__ == "__main__":
    main()
