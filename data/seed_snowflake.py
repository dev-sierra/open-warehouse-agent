"""Seed the Snowflake demo database with the synthetic settlement dataset.

Requires the same env vars as connector.snowflake_adapter (see .env.example)
plus a role with CREATE TABLE on the target schema (infra/snowflake_bootstrap.py
already grants this to OWA_APP_ROLE).

Usage: uv run python -m data.seed_snowflake
"""

from __future__ import annotations

import os

import snowflake.connector

from connector.snowflake_adapter import _load_private_key
from data.generator import generate

SCHEMA_SQL = """
create table products (
    product_id integer primary key,
    name varchar not null,
    category varchar not null
);

create table orders (
    order_id integer primary key,
    product_id integer not null references products(product_id),
    customer_email varchar not null,
    channel varchar not null,
    order_amount decimal(10,2) not null,
    order_date date not null
);

create table settlements (
    settlement_id integer primary key,
    order_id integer not null references orders(order_id),
    channel varchar not null,
    gross_amount decimal(10,2) not null,
    fee_amount decimal(10,2) not null,
    net_amount decimal(10,2) not null,
    settlement_date date not null
);
"""


def seed() -> None:
    dataset = generate()
    connect_kwargs = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    private_key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    if private_key_path:
        connect_kwargs["private_key"] = _load_private_key(private_key_path)
    else:
        connect_kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]

    conn = snowflake.connector.connect(**connect_kwargs)
    try:
        cursor = conn.cursor()
        cursor.execute("drop table if exists settlements")
        cursor.execute("drop table if exists orders")
        cursor.execute("drop table if exists products")
        for statement in SCHEMA_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

        cursor.executemany(
            "insert into products values (%s, %s, %s)",
            [(p.product_id, p.name, p.category) for p in dataset.products],
        )
        cursor.executemany(
            "insert into orders values (%s, %s, %s, %s, %s, %s)",
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
            ],
        )
        cursor.executemany(
            "insert into settlements values (%s, %s, %s, %s, %s, %s, %s)",
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
            ],
        )
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print("seeded Snowflake OWA_DEMO.PUBLIC")
