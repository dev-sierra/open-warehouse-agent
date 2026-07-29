"""One-time Snowflake provisioning for the demo warehouse.

Connects with your personal SSO session (externalbrowser auth, as
ACCOUNTADMIN) and creates the least-privilege pieces the running agent
actually uses: a database/schema, a scoped role, and a service user
authenticated by an RSA key pair (no password, no browser popup needed
at agent runtime).

Usage:
    uv run python -m infra.snowflake_bootstrap

Requires SNOWFLAKE_ACCOUNT and SNOWFLAKE_ADMIN_USER in the environment;
reads the public key from .secrets/owa_app_user_key.pub. Safe to re-run
(everything is CREATE ... IF NOT EXISTS / CREATE OR REPLACE for the key).

Auth: if SNOWFLAKE_ADMIN_PASSWORD is set, uses plain password auth;
otherwise falls back to externalbrowser (SSO) -- only works if the
account actually has a SAML integration configured.
"""

from __future__ import annotations

import os
from pathlib import Path

import snowflake.connector

WAREHOUSE = "COMPUTE_WH"
DATABASE = "OWA_DEMO"
SCHEMA = "PUBLIC"
ROLE = "OWA_APP_ROLE"
APP_USER = "OWA_APP_USER"
PUBLIC_KEY_PATH = Path(".secrets/owa_app_user_key.pub")

STATEMENTS = [
    f"CREATE DATABASE IF NOT EXISTS {DATABASE}",
    f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}",
    f"CREATE ROLE IF NOT EXISTS {ROLE}",
    f"GRANT USAGE ON WAREHOUSE {WAREHOUSE} TO ROLE {ROLE}",
    f"GRANT USAGE ON DATABASE {DATABASE} TO ROLE {ROLE}",
    f"GRANT USAGE ON SCHEMA {DATABASE}.{SCHEMA} TO ROLE {ROLE}",
    f"GRANT CREATE TABLE ON SCHEMA {DATABASE}.{SCHEMA} TO ROLE {ROLE}",
    f"GRANT SELECT ON FUTURE TABLES IN SCHEMA {DATABASE}.{SCHEMA} TO ROLE {ROLE}",
    f"GRANT SELECT ON ALL TABLES IN SCHEMA {DATABASE}.{SCHEMA} TO ROLE {ROLE}",
]


def _public_key_body(pem: str) -> str:
    lines = [line for line in pem.strip().splitlines() if "BEGIN" not in line and "END" not in line]
    return "".join(lines)


def main() -> None:
    account = os.environ["SNOWFLAKE_ACCOUNT"]
    admin_user = os.environ["SNOWFLAKE_ADMIN_USER"]
    admin_password = os.environ.get("SNOWFLAKE_ADMIN_PASSWORD")
    public_key = _public_key_body(PUBLIC_KEY_PATH.read_text())

    connect_kwargs = dict(
        account=account,
        user=admin_user,
        role="ACCOUNTADMIN",
        warehouse=WAREHOUSE,
    )
    if admin_password:
        connect_kwargs["password"] = admin_password
    else:
        connect_kwargs["authenticator"] = "externalbrowser"

    conn = snowflake.connector.connect(**connect_kwargs)
    try:
        cursor = conn.cursor()
        for stmt in STATEMENTS:
            print(f"> {stmt}")
            cursor.execute(stmt)

        create_user_sql = f"""
            CREATE USER IF NOT EXISTS {APP_USER}
                RSA_PUBLIC_KEY = '{public_key}'
                DEFAULT_ROLE = {ROLE}
                DEFAULT_WAREHOUSE = {WAREHOUSE}
                DEFAULT_NAMESPACE = {DATABASE}.{SCHEMA}
        """
        print(f"> {create_user_sql.strip()}")
        cursor.execute(create_user_sql)

        alter_key_sql = f"ALTER USER {APP_USER} SET RSA_PUBLIC_KEY = '{public_key}'"
        print(f"> {alter_key_sql}")
        cursor.execute(alter_key_sql)

        grant_role_sql = f"GRANT ROLE {ROLE} TO USER {APP_USER}"
        print(f"> {grant_role_sql}")
        cursor.execute(grant_role_sql)

        print(f"\nProvisioned: database={DATABASE} schema={SCHEMA} role={ROLE} user={APP_USER}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
