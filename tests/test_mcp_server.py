import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from connector.duckdb_adapter import DuckDBConnector
from data.seed_duckdb import seed
from mcp_server.audit import AuditLog
from mcp_server.server import build_server


@pytest.fixture
def server(tmp_path):
    db_path = tmp_path / "warehouse.duckdb"
    seed(db_path)
    connector = DuckDBConnector(db_path)
    audit_log = AuditLog(tmp_path / "audit.jsonl")
    yield build_server(connector, audit_log), tmp_path / "audit.jsonl"
    connector.close()


def _first_json(content_blocks):
    return json.loads(content_blocks[0].text)


async def test_list_tables_tool(server):
    # list-returning tools come back as (content_blocks, {"result": [...]})
    # while dict-returning tools (run_query below) come back as just
    # content_blocks — an inconsistency in the mcp SDK's convert_result,
    # not something we control.
    mcp, _ = server
    _, structured = await mcp.call_tool("list_tables", {})
    tables = [table["name"] for table in structured["result"]]
    assert set(tables) == {"products", "orders", "settlements"}


async def test_run_query_tool_returns_rows(server):
    mcp, _ = server
    content = await mcp.call_tool("run_query", {"sql": "select 1 as x"})
    payload = _first_json(content)
    assert payload["columns"] == ["x"]
    assert payload["row_count"] == 1


async def test_run_query_tool_rejects_unsafe_sql(server):
    mcp, _ = server
    with pytest.raises(ToolError):
        await mcp.call_tool("run_query", {"sql": "drop table products"})


async def test_run_query_tool_writes_audit_log(server):
    mcp, audit_path = server
    await mcp.call_tool("run_query", {"sql": "select 1"})
    try:
        await mcp.call_tool("run_query", {"sql": "drop table products"})
    except ToolError:
        pass

    lines = audit_path.read_text().splitlines()
    assert len(lines) == 2
    success_record = json.loads(lines[0])
    failure_record = json.loads(lines[1])
    assert success_record["success"] is True
    assert failure_record["success"] is False
    assert "only SELECT statements are allowed" in failure_record["error"]
