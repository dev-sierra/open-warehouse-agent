"""SELECT-only enforcement and row-limit clamping, shared by every adapter.

Every WarehouseConnector.run_query implementation must call
enforce_select_only() before executing anything the model produced.
This is the boundary that turns "an LLM wrote some SQL" into "an LLM
wrote a query that is provably incapable of mutating or exfiltrating
more than row_limit rows of your warehouse."
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp


class UnsafeQueryError(ValueError):
    """Raised when a query is not a single, standalone SELECT statement."""


def enforce_select_only(sql: str, dialect: str) -> exp.Select:
    """Parse sql and return it as a Select expression, or raise.

    Rejects: anything that isn't exactly one statement, anything that
    doesn't parse to a SELECT (INSERT/UPDATE/DELETE/DDL/CALL/etc.), and
    multi-statement input (e.g. "SELECT 1; DROP TABLE x") — sqlglot's
    parse() splits on ";", so more than one resulting statement is
    itself a rejection reason.
    """
    try:
        statements = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError as e:
        raise UnsafeQueryError(f"could not parse query: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise UnsafeQueryError("exactly one SQL statement is required")

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        raise UnsafeQueryError(
            f"only SELECT statements are allowed, got {type(statement).__name__}"
        )

    return statement


def apply_row_limit(select: exp.Select, max_rows: int, dialect: str) -> str:
    """Return SQL for select with a LIMIT clamped to at most max_rows.

    If the query already has a LIMIT, it's lowered to max_rows when it
    exceeds it. If it has none, max_rows is added.
    """
    existing_limit = select.args.get("limit")
    if existing_limit is not None:
        try:
            requested = int(existing_limit.expression.this)
        except (AttributeError, TypeError, ValueError):
            requested = max_rows
        if requested > max_rows:
            select = select.limit(max_rows, copy=True)
    else:
        select = select.limit(max_rows, copy=True)

    return select.sql(dialect=dialect)
