"""Seed the Databricks demo schema with the synthetic settlement dataset.

Requires the same env vars as connector.databricks_adapter (see
.env.example). The service principal needs CREATE TABLE + SELECT on the
target schema (infra/databricks_bootstrap.py already grants this).

Usage: uv run python -m data.seed_databricks
"""

from __future__ import annotations

import datetime
import os

from databricks import sql

from connector.databricks_adapter import _fetch_oauth_token
from data.generator import generate

SCHEMA_SQL = """
create table products (
    product_id int not null,
    name string not null,
    category string not null
);

create table orders (
    order_id int not null,
    product_id int not null,
    customer_email string not null,
    channel string not null,
    order_amount decimal(10,2) not null,
    order_date date not null
);

create table settlements (
    settlement_id int not null,
    order_id int not null,
    channel string not null,
    gross_amount decimal(10,2) not null,
    fee_amount decimal(10,2) not null,
    net_amount decimal(10,2) not null,
    settlement_date date not null
);
"""


def _sql_literal(value) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, datetime.date):
        return f"DATE'{value.isoformat()}'"
    return str(value)


def _values_clause(rows: list[tuple]) -> str:
    return ", ".join("(" + ", ".join(_sql_literal(v) for v in row) + ")" for row in rows)


def seed() -> None:
    dataset = generate()
    hostname = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    client_id = os.environ.get("DATABRICKS_CLIENT_ID")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")
    access_token = (
        _fetch_oauth_token(hostname, client_id, client_secret)
        if client_id and client_secret
        else os.environ["DATABRICKS_TOKEN"]
    )

    conn = sql.connect(
        server_hostname=hostname,
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=access_token,
        catalog=os.environ["DATABRICKS_CATALOG"],
        schema=os.environ.get("DATABRICKS_SCHEMA", "default"),
    )
    try:
        cursor = conn.cursor()
        cursor.execute("drop table if exists settlements")
        cursor.execute("drop table if exists orders")
        cursor.execute("drop table if exists products")
        for statement in SCHEMA_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

        # A single multi-row INSERT per table rather than executemany --
        # executemany sends one round-trip per row, which against a cloud
        # SQL warehouse takes minutes for a few hundred rows instead of
        # seconds. Values come from our own trusted generator, not
        # untrusted input, so inline literals (rather than bind params)
        # are an acceptable tradeoff here.
        cursor.execute(
            "insert into products values "
            + _values_clause([(p.product_id, p.name, p.category) for p in dataset.products])
        )
        cursor.execute(
            "insert into orders values "
            + _values_clause(
                [
                    (
                        o.order_id,
                        o.product_id,
                        o.customer_email,
                        o.channel,
                        o.order_amount,
                        o.order_date,
                    )
                    for o in dataset.orders
                ]
            )
        )
        cursor.execute(
            "insert into settlements values "
            + _values_clause(
                [
                    (
                        s.settlement_id,
                        s.order_id,
                        s.channel,
                        s.gross_amount,
                        s.fee_amount,
                        s.net_amount,
                        s.settlement_date,
                    )
                    for s in dataset.settlements
                ]
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print("seeded Databricks owa_demo.default")
