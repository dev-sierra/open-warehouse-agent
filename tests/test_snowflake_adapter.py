"""Live Snowflake adapter tests.

Skipped unless SNOWFLAKE_ACCOUNT is set, since these hit a real account
(the OWA_DEMO database provisioned by infra/snowflake_bootstrap.py) rather
than a local fixture like the DuckDB adapter tests. Run seed first:
    uv run python -m data.seed_snowflake
"""

import os

import pytest

from connector.sql_guard import UnsafeQueryError

pytestmark = pytest.mark.skipif(
    "SNOWFLAKE_ACCOUNT" not in os.environ,
    reason="no live Snowflake account configured (set SNOWFLAKE_ACCOUNT and friends)",
)


@pytest.fixture
def connector():
    from connector.snowflake_adapter import SnowflakeConnector

    conn = SnowflakeConnector()
    yield conn
    conn.close()


def test_list_tables_returns_seeded_tables(connector):
    tables = {ref.name for ref in connector.list_tables()}
    assert tables == {"PRODUCTS", "ORDERS", "SETTLEMENTS"}


def test_describe_table_returns_columns(connector):
    schema = connector.describe_table("PRODUCTS")
    assert schema.name == "PRODUCTS"
    column_names = {c.name for c in schema.columns}
    assert column_names == {"PRODUCT_ID", "NAME", "CATEGORY"}


def test_describe_table_raises_for_unknown_table(connector):
    with pytest.raises(ValueError):
        connector.describe_table("DOES_NOT_EXIST")


def test_run_query_returns_rows(connector):
    result = connector.run_query("select product_id, name from products order by product_id")
    assert result.row_count == 20
    assert not result.truncated


def test_run_query_enforces_row_limit(connector):
    result = connector.run_query("select * from orders", row_limit=10)
    assert result.row_count == 10
    assert result.truncated


def test_run_query_rejects_non_select(connector):
    with pytest.raises(UnsafeQueryError):
        connector.run_query("drop table products")


def test_run_query_rejects_dml_hidden_in_select_shaped_string(connector):
    with pytest.raises(UnsafeQueryError):
        connector.run_query("select 1; delete from products")
