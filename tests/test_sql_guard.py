import pytest

from connector.sql_guard import UnsafeQueryError, apply_row_limit, enforce_select_only


def test_select_is_allowed():
    select = enforce_select_only("select 1", dialect="duckdb")
    assert select.sql(dialect="duckdb") == "SELECT 1"


@pytest.mark.parametrize(
    "sql",
    [
        "insert into t values (1)",
        "update t set x = 1",
        "delete from t",
        "drop table t",
        "create table t (x int)",
        "alter table t add column y int",
        "call some_procedure()",
    ],
)
def test_dml_ddl_is_rejected(sql):
    with pytest.raises(UnsafeQueryError):
        enforce_select_only(sql, dialect="duckdb")


def test_multiple_statements_are_rejected():
    with pytest.raises(UnsafeQueryError):
        enforce_select_only("select 1; drop table t", dialect="duckdb")


def test_unparseable_sql_is_rejected():
    with pytest.raises(UnsafeQueryError):
        enforce_select_only("select select select from from", dialect="duckdb")


def test_row_limit_is_added_when_absent():
    select = enforce_select_only("select * from t", dialect="duckdb")
    sql = apply_row_limit(select, max_rows=100, dialect="duckdb")
    assert "LIMIT 100" in sql


def test_row_limit_is_clamped_when_too_high():
    select = enforce_select_only("select * from t limit 10000", dialect="duckdb")
    sql = apply_row_limit(select, max_rows=100, dialect="duckdb")
    assert "LIMIT 100" in sql
    assert "LIMIT 10000" not in sql


def test_row_limit_is_kept_when_already_below_max():
    select = enforce_select_only("select * from t limit 5", dialect="duckdb")
    sql = apply_row_limit(select, max_rows=100, dialect="duckdb")
    assert "LIMIT 5" in sql
