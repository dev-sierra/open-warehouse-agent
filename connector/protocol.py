"""Connector protocol every warehouse adapter implements.

The MCP server (see mcp_server/) is written against this protocol only —
it never imports a specific backend. That's what lets the same three
tools (list_tables, describe_table, run_query) run against DuckDB,
Snowflake, or Databricks interchangeably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    nullable: bool


@dataclass(frozen=True)
class TableRef:
    schema: str
    name: str


@dataclass(frozen=True)
class TableSchema:
    schema: str
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    row_count: int
    truncated: bool


class WarehouseConnector(Protocol):
    """A read-only handle onto one warehouse backend.

    `dialect` must be a sqlglot-recognized dialect name (e.g. "duckdb",
    "snowflake") — the SQL guard uses it to parse queries correctly
    before they're allowed to run.
    """

    dialect: str

    def list_tables(self, schema: str | None = None) -> list[TableRef]:
        """List tables, optionally scoped to one schema."""
        ...

    def describe_table(self, table: str, schema: str | None = None) -> TableSchema:
        """Return column names, types, and nullability for one table."""
        ...

    def run_query(self, sql: str, row_limit: int = 1000) -> QueryResult:
        """Execute a SELECT-only query and return up to row_limit rows.

        Implementations must reject anything that isn't a single SELECT
        (see connector.sql_guard) — this is the last line of defense
        against a model-generated DML/DDL statement, independent of
        whatever the MCP server layer already checked.
        """
        ...
