"""One-time Databricks provisioning for the demo catalog/schema.

Connects with an admin-capable PAT and creates the least-privilege
pieces the running agent actually uses: a Unity Catalog catalog/schema,
and grants to the service principal (created via the workspace UI --
see README) that the app authenticates as.

Usage:
    uv run python -m infra.databricks_bootstrap

Requires DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH,
DATABRICKS_ADMIN_TOKEN, DATABRICKS_CATALOG, DATABRICKS_SCHEMA, and
DATABRICKS_CLIENT_ID (the service principal to grant access to) in the
environment. Safe to re-run (everything is CREATE ... IF NOT EXISTS /
idempotent GRANTs).
"""

from __future__ import annotations

import os

from databricks import sql


def main() -> None:
    catalog = os.environ["DATABRICKS_CATALOG"]
    schema = os.environ.get("DATABRICKS_SCHEMA", "default")
    principal = os.environ["DATABRICKS_CLIENT_ID"]

    conn = sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_ADMIN_TOKEN"],
    )
    try:
        cursor = conn.cursor()
        statements = [
            f"CREATE CATALOG IF NOT EXISTS {catalog}",
            f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}",
            f"GRANT USE CATALOG ON CATALOG {catalog} TO `{principal}`",
            f"GRANT USE SCHEMA ON SCHEMA {catalog}.{schema} TO `{principal}`",
            f"GRANT SELECT ON SCHEMA {catalog}.{schema} TO `{principal}`",
            f"GRANT CREATE TABLE ON SCHEMA {catalog}.{schema} TO `{principal}`",
        ]
        for stmt in statements:
            print(f"> {stmt}")
            cursor.execute(stmt)

        print(f"\nProvisioned: catalog={catalog} schema={schema} principal={principal}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
