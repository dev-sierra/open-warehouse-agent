"""Snowflake adapter.

Requires the optional `snowflake` extra (`uv sync --extra snowflake`)
and a Snowflake account. Verified against a live trial account using
a dedicated least-privilege service user (see infra/snowflake_bootstrap.py).
Follows the same contract as connector.duckdb_adapter.DuckDBConnector
and is exercised by the same adapter contract tests.

Credentials are read from environment variables, never hardcoded or
passed through the model:
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_WAREHOUSE,
    SNOWFLAKE_DATABASE, SNOWFLAKE_ROLE (optional)

Auth is key-pair by default (SNOWFLAKE_PRIVATE_KEY_PATH pointing at an
unencrypted PKCS8 .p8 file) since the service user has no password.
Falls back to SNOWFLAKE_PASSWORD if set, for accounts provisioned the
older way.
"""

from __future__ import annotations

import os

import snowflake.connector
from cryptography.hazmat.primitives import serialization

from connector.protocol import ColumnInfo, QueryResult, TableRef, TableSchema
from connector.sql_guard import apply_row_limit, enforce_select_only


def _load_private_key(path: str) -> bytes:
    with open(path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class SnowflakeConnector:
    dialect = "snowflake"

    def __init__(self, database: str | None = None):
        self._database = database or os.environ["SNOWFLAKE_DATABASE"]
        connect_kwargs = dict(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
            database=self._database,
            role=os.environ.get("SNOWFLAKE_ROLE"),
        )
        private_key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
        if private_key_path:
            connect_kwargs["private_key"] = _load_private_key(private_key_path)
        else:
            connect_kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
        self._conn = snowflake.connector.connect(**connect_kwargs)

    def list_tables(self, schema: str | None = None) -> list[TableRef]:
        schema = schema or "PUBLIC"
        cursor = self._conn.cursor()
        cursor.execute(
            """
            select table_schema, table_name
            from information_schema.tables
            where table_schema = %s
            order by table_name
            """,
            (schema,),
        )
        return [TableRef(schema=row[0], name=row[1]) for row in cursor.fetchall()]

    def describe_table(self, table: str, schema: str | None = None) -> TableSchema:
        schema = schema or "PUBLIC"
        cursor = self._conn.cursor()
        cursor.execute(
            """
            select column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = %s and table_name = %s
            order by ordinal_position
            """,
            (schema, table),
        )
        rows = cursor.fetchall()
        if not rows:
            raise ValueError(f"table not found: {schema}.{table}")

        columns = [
            ColumnInfo(name=row[0], type=row[1], nullable=row[2] == "YES") for row in rows
        ]
        return TableSchema(schema=schema, name=table, columns=columns)

    def run_query(self, sql: str, row_limit: int = 1000) -> QueryResult:
        select = enforce_select_only(sql, dialect=self.dialect)
        limited_sql = apply_row_limit(select, max_rows=row_limit, dialect=self.dialect)

        cursor = self._conn.cursor()
        cursor.execute(limited_sql)
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
