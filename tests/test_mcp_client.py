import json

import pytest
from mcp import types

from agent.mcp_client import MCPToolClient, ToolExecutionError, _first_text


def test_first_text_returns_first_text_block():
    blocks = [
        types.ImageContent(type="image", data="abc", mimeType="image/png"),
        types.TextContent(type="text", text="hello"),
        types.TextContent(type="text", text="second"),
    ]
    assert _first_text(blocks) == "hello"


def test_first_text_returns_none_when_no_text_block():
    blocks = [types.ImageContent(type="image", data="abc", mimeType="image/png")]
    assert _first_text(blocks) is None


class _FakeSession:
    def __init__(self, result):
        self._result = result

    async def call_tool(self, name, arguments):
        return self._result


async def test_call_tool_returns_text_content_on_success():
    client = MCPToolClient()
    client._session = _FakeSession(
        types.CallToolResult(content=[types.TextContent(type="text", text="3 tables")])
    )

    result = await client.call_tool("list_tables", {})

    assert result == "3 tables"


async def test_call_tool_returns_structured_content_when_present():
    client = MCPToolClient()
    client._session = _FakeSession(
        types.CallToolResult(
            content=[types.TextContent(type="text", text="ignored")],
            structuredContent={"row_count": 3},
        )
    )

    result = await client.call_tool("list_tables", {})

    assert result == json.dumps({"row_count": 3})


async def test_call_tool_raises_on_error_result():
    client = MCPToolClient()
    client._session = _FakeSession(
        types.CallToolResult(
            content=[types.TextContent(type="text", text="unsafe query")],
            isError=True,
        )
    )

    with pytest.raises(ToolExecutionError, match="unsafe query"):
        await client.call_tool("run_query", {"sql": "drop table x"})
