"""DuckDB adapter — the zero-cloud-account path.

Anyone can run the full demo against a local .duckdb file with no
warehouse account of any kind. This is also the adapter the CI test
suite runs the contract tests against.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from connector.protocol import ColumnInfo, QueryResult, TableRef, TableSchema
from connector.sql_guard import apply_row_limit, enforce_select_only

DEFAULT_SCHEMA = "main"


class DuckDBConnector:
    dialect = "duckdb"

    def __init__(self, database_path: str | Path):
        self._conn = duckdb.connect(str(database_path), read_only=False)

    def list_tables(self, schema: str | None = None) -> list[TableRef]:
        schema = schema or DEFAULT_SCHEMA
        rows = self._conn.execute(
            """
            select table_schema, table_name
            from information_schema.tables
            where table_schema = ?
            order by table_name
            """,
            [schema],
        ).fetchall()
        return [TableRef(schema=row[0], name=row[1]) for row in rows]

    def describe_table(self, table: str, schema: str | None = None) -> TableSchema:
        schema = schema or DEFAULT_SCHEMA
        rows = self._conn.execute(
            """
            select column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = ? and table_name = ?
            order by ordinal_position
            """,
            [schema, table],
        ).fetchall()
        if not rows:
            raise ValueError(f"table not found: {schema}.{table}")

        columns = [
            ColumnInfo(name=row[0], type=row[1], nullable=row[2] == "YES") for row in rows
        ]
        return TableSchema(schema=schema, name=table, columns=columns)

    def run_query(self, sql: str, row_limit: int = 1000) -> QueryResult:
        select = enforce_select_only(sql, dialect=self.dialect)
        limited_sql = apply_row_limit(select, max_rows=row_limit, dialect=self.dialect)

        cursor = self._conn.execute(limited_sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=len(rows) >= row_limit,
        )

    def close(self) -> None:
        self._conn.close()
