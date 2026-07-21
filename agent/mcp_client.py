"""Async wrapper around the MCP stdio client.

Spawns `python -m mcp_server` as a subprocess and speaks MCP over stdio —
this is the client-side counterpart to mcp_server/server.py's FastMCP
server, matching the README architecture diagram's CLI -> MCP server
boundary (arrow A).
"""

from __future__ import annotations

import json
import sys
from contextlib import AsyncExitStack

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class ToolExecutionError(RuntimeError):
    """Raised when an MCP tool call comes back with isError=True."""


class MCPToolClient:
    """Async context manager owning one mcp_server subprocess + session."""

    def __init__(self, command: str = sys.executable, args: list[str] | None = None) -> None:
        self._params = StdioServerParameters(command=command, args=args or ["-m", "mcp_server"])
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> MCPToolClient:
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        assert self._stack is not None
        await self._stack.aclose()
        self._stack = None
        self._session = None

    async def list_tools(self) -> list[types.Tool]:
        assert self._session is not None, "MCPToolClient must be used as an async context manager"
        result = await self._session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        assert self._session is not None, "MCPToolClient must be used as an async context manager"
        result = await self._session.call_tool(name, arguments)
        if result.isError:
            raise ToolExecutionError(_first_text(result.content) or f"{name} failed")
        if result.structuredContent is not None:
            return json.dumps(result.structuredContent)
        return _first_text(result.content) or "null"


def _first_text(content_blocks: list[types.ContentBlock]) -> str | None:
    for block in content_blocks:
        if isinstance(block, types.TextContent):
            return block.text
    return None
