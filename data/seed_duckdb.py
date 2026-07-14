"""Seed a DuckDB file with the synthetic settlement dataset.

Usage: uv run python -m data.seed_duckdb [path/to/warehouse.duckdb]
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

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

DEFAULT_PATH = "data/warehouse.duckdb"


def seed(database_path: str | Path) -> None:
    dataset = generate()
    conn = duckdb.connect(str(database_path))
    try:
        conn.execute("drop table if exists settlements")
        conn.execute("drop table if exists orders")
        conn.execute("drop table if exists products")
        conn.execute(SCHEMA_SQL)

        conn.executemany(
            "insert into products values (?, ?, ?)",
            [(p.product_id, p.name, p.category) for p in dataset.products],
        )
        conn.executemany(
            "insert into orders values (?, ?, ?, ?, ?, ?)",
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
        conn.executemany(
            "insert into settlements values (?, ?, ?, ?, ?, ?, ?)",
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
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    seed(target)
    print(f"seeded {target}")
