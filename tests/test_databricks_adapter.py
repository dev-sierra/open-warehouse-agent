"""Live Databricks adapter tests.

Skipped unless DATABRICKS_SERVER_HOSTNAME is set, since these hit a real
workspace (the owa_demo.default schema provisioned by
infra/databricks_bootstrap.py) rather than a local fixture. Run seed
first:
    uv run python -m data.seed_databricks
"""

import os

import pytest

from connector.sql_guard import UnsafeQueryError

pytestmark = pytest.mark.skipif(
    "DATABRICKS_SERVER_HOSTNAME" not in os.environ,
    reason="no live Databricks workspace configured (set DATABRICKS_SERVER_HOSTNAME and friends)",
)


@pytest.fixture
def connector():
    from connector.databricks_adapter import DatabricksConnector

    conn = DatabricksConnector()
    yield conn
    conn.close()


def test_list_tables_returns_seeded_tables(connector):
    tables = {ref.name for ref in connector.list_tables()}
    assert tables == {"products", "orders", "settlements"}


def test_describe_table_returns_columns(connector):
    schema = connector.describe_table("products")
    assert schema.name == "products"
    column_names = {c.name for c in schema.columns}
    assert column_names == {"product_id", "name", "category"}


def test_describe_table_raises_for_unknown_table(connector):
    with pytest.raises(ValueError):
        connector.describe_table("does_not_exist")


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
