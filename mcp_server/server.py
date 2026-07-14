"""FastMCP server exposing the three warehouse tools.

build_server() is written against connector.protocol.WarehouseConnector
only, never a specific backend — the same server works unmodified
against DuckDB, Snowflake, or Databricks by swapping the connector
passed in.
"""

from __future__ import annotations

import time

from mcp.server.fastmcp import FastMCP

from connector.protocol import WarehouseConnector
from connector.sql_guard import UnsafeQueryError
from mcp_server.audit import AuditLog, AuditRecord

MAX_ROW_LIMIT = 1000


def build_server(
    connector: WarehouseConnector,
    audit_log: AuditLog,
    max_row_limit: int = MAX_ROW_LIMIT,
) -> FastMCP:
    mcp = FastMCP("warehouse")

    @mcp.tool()
    def list_tables(schema: str | None = None) -> list[dict]:
        """List tables in the warehouse, optionally scoped to one schema."""
        return [
            {"schema": ref.schema, "name": ref.name} for ref in connector.list_tables(schema)
        ]

    @mcp.tool()
    def describe_table(table: str, schema: str | None = None) -> dict:
        """Return column names, types, and nullability for one table."""
        table_schema = connector.describe_table(table, schema)
        return {
            "schema": table_schema.schema,
            "name": table_schema.name,
            "columns": [
                {"name": c.name, "type": c.type, "nullable": c.nullable}
                for c in table_schema.columns
            ],
        }

    @mcp.tool()
    def run_query(sql: str, row_limit: int = max_row_limit) -> dict:
        """Run a read-only SELECT query and return up to row_limit rows.

        Only SELECT statements are allowed; anything else is rejected.
        """
        row_limit = min(row_limit, max_row_limit)
        start = time.monotonic()
        try:
            result = connector.run_query(sql, row_limit=row_limit)
        except (UnsafeQueryError, ValueError) as e:
            audit_log.record(
                AuditRecord(
                    timestamp=time.time(),
                    sql=sql,
                    row_limit=row_limit,
                    success=False,
                    error=str(e),
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            )
            raise

        audit_log.record(
            AuditRecord(
                timestamp=time.time(),
                sql=sql,
                row_limit=row_limit,
                success=True,
                row_count=result.row_count,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        )
        return {
            "columns": result.columns,
            "rows": [list(row) for row in result.rows],
            "row_count": result.row_count,
            "truncated": result.truncated,
        }

    return mcp
