"""Databricks adapter.

Requires the optional `databricks` extra (`uv sync --extra databricks`)
and a Databricks workspace with Unity Catalog and a SQL warehouse.
Verified against a live trial workspace using a dedicated least-privilege
service principal (see infra/databricks_bootstrap.py). Follows the same
contract as connector.duckdb_adapter.DuckDBConnector and is exercised by
the same adapter contract tests.

Credentials are read from environment variables, never hardcoded or
passed through the model:
    DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH,
    DATABRICKS_CATALOG, DATABRICKS_SCHEMA (optional, default "default")

Auth is OAuth client-credentials (service principal) by default via
DATABRICKS_CLIENT_ID/DATABRICKS_CLIENT_SECRET. databricks-sql-connector's
built-in service-principal auth (auth_type="azure-sp-m2m") is Azure-only,
so for AWS/GCP workspaces we fetch a bearer token ourselves against
Databricks' documented OAuth token endpoint (POST .../oidc/v1/token,
client_credentials grant) and hand it to the connector as a plain
access_token. Falls back to DATABRICKS_TOKEN (a PAT) if no client
id/secret is set.
"""

from __future__ import annotations

import os

import httpx
from databricks import sql

from connector.protocol import ColumnInfo, QueryResult, TableRef, TableSchema
from connector.sql_guard import apply_row_limit, enforce_select_only


def _fetch_oauth_token(hostname: str, client_id: str, client_secret: str) -> str:
    response = httpx.post(
        f"https://{hostname}/oidc/v1/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials", "scope": "all-apis"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


class DatabricksConnector:
    dialect = "databricks"

    def __init__(self, catalog: str | None = None, schema: str | None = None):
        self._catalog = catalog or os.environ["DATABRICKS_CATALOG"]
        self._schema = schema or os.environ.get("DATABRICKS_SCHEMA", "default")
        hostname = os.environ["DATABRICKS_SERVER_HOSTNAME"]

        client_id = os.environ.get("DATABRICKS_CLIENT_ID")
        client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")
        if client_id and client_secret:
            access_token = _fetch_oauth_token(hostname, client_id, client_secret)
        else:
            access_token = os.environ["DATABRICKS_TOKEN"]

        self._conn = sql.connect(
            server_hostname=hostname,
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=access_token,
            catalog=self._catalog,
            schema=self._schema,
        )

    def list_tables(self, schema: str | None = None) -> list[TableRef]:
        schema = schema or self._schema
        cursor = self._conn.cursor()
        cursor.execute(
            """
            select table_schema, table_name
            from information_schema.tables
            where table_schema = ?
            order by table_name
            """,
            (schema,),
        )
        return [TableRef(schema=row[0], name=row[1]) for row in cursor.fetchall()]

    def describe_table(self, table: str, schema: str | None = None) -> TableSchema:
        schema = schema or self._schema
        cursor = self._conn.cursor()
        cursor.execute(
            """
            select column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = ? and table_name = ?
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

    def run_query(self, sql_text: str, row_limit: int = 1000) -> QueryResult:
        select = enforce_select_only(sql_text, dialect=self.dialect)
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
