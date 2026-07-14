import pytest

from connector.duckdb_adapter import DuckDBConnector
from connector.sql_guard import UnsafeQueryError
from data.seed_duckdb import seed


@pytest.fixture
def connector(tmp_path):
    db_path = tmp_path / "warehouse.duckdb"
    seed(db_path)
    conn = DuckDBConnector(db_path)
    yield conn
    conn.close()


def test_list_tables_returns_seeded_tables(connector):
    tables = {ref.name for ref in connector.list_tables()}
    assert tables == {"products", "orders", "settlements"}


def test_describe_table_returns_columns(connector):
    schema = connector.describe_table("products")
    assert schema.schema == "main"
    assert schema.name == "products"
    column_names = {c.name for c in schema.columns}
    assert column_names == {"product_id", "name", "category"}


def test_describe_table_raises_for_unknown_table(connector):
    with pytest.raises(ValueError):
        connector.describe_table("does_not_exist")


def test_run_query_returns_rows(connector):
    result = connector.run_query("select product_id, name from products order by product_id")
    assert result.columns == ["product_id", "name"]
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


def test_demo_question_stripe_settlement_total_by_product(connector):
    result = connector.run_query(
        """
        select p.name, sum(s.gross_amount) as total
        from settlements s
        join orders o on s.order_id = o.order_id
        join products p on o.product_id = p.product_id
        where s.channel = 'stripe' and date_trunc('month', s.settlement_date) = date '2024-08-01'
        group by p.name
        order by total desc
        """
    )
    assert result.columns == ["name", "total"]
    assert result.row_count > 0
