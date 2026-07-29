"""Entry point: uv run python -m mcp_server

Runs the MCP server over stdio against a local DuckDB file by default —
the zero-cloud-account path. Override WAREHOUSE_DB_PATH /
WAREHOUSE_AUDIT_PATH to point elsewhere, or WAREHOUSE_BACKEND to switch
to another adapter (see mcp_server/backends.py for supported names).
"""

from __future__ import annotations

import os

from mcp_server.audit import AuditLog
from mcp_server.backends import build_connector
from mcp_server.server import build_server

DEFAULT_DB_PATH = "data/warehouse.duckdb"
DEFAULT_AUDIT_PATH = "data/audit.jsonl"
DEFAULT_BACKEND = "duckdb"


def main() -> None:
    backend = os.environ.get("WAREHOUSE_BACKEND", DEFAULT_BACKEND)
    db_path = os.environ.get("WAREHOUSE_DB_PATH", DEFAULT_DB_PATH)
    audit_path = os.environ.get("WAREHOUSE_AUDIT_PATH", DEFAULT_AUDIT_PATH)

    connector = build_connector(backend, db_path=db_path)
    audit_log = AuditLog(audit_path)
    server = build_server(connector, audit_log)
    server.run()


if __name__ == "__main__":
    main()
