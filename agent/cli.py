"""Interactive CLI chat host: `uv run python -m agent`.

Spawns the MCP server as a subprocess, points the OpenAI-compatible
client at a local Ollama server, and runs the tool-calling loop from
agent/loop.py for each question the user types.
"""

from __future__ import annotations

import asyncio

from openai import APIConnectionError

from agent.llm_client import build_chat_fn, build_client, mcp_tools_to_openai, model_name
from agent.loop import DEFAULT_SYSTEM_PROMPT, AgentLoopError, run_agent_loop
from agent.mcp_client import MCPToolClient, ToolExecutionError


def _truncate(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def _amain() -> None:
    print("open-warehouse-agent — ask a question about orders/settlements (Ctrl-D to quit)")
    async with MCPToolClient() as mcp_client:
        tools = await mcp_client.list_tools()
        openai_tools = mcp_tools_to_openai(tools)
        client = build_client()
        model = model_name()
        chat_fn = build_chat_fn(client, model, openai_tools)

        # Pre-fetch the table list once per session and fold it into the
        # system prompt. list_tables is free and side-effect-free, so
        # there's no cost to always having it in context — and it removes
        # a real failure mode where the model stalls instead of exploring
        # the schema when a question uses vague business terms (e.g.
        # "sales") that don't obviously match a table name.
        table_list = await mcp_client.call_tool("list_tables", {})
        system_prompt = (
            f"{DEFAULT_SYSTEM_PROMPT}\n\nThe warehouse's tables (from "
            f"list_tables, already fetched for you): {table_list}"
        )

        async def tool_executor(name: str, arguments: dict) -> str:
            # Feed tool failures (bad SQL, unknown table, ...) back to the
            # model as the tool result rather than aborting the question —
            # a wrong column name is exactly the kind of mistake a small
            # model can self-correct on the next turn if it sees the error.
            try:
                return await mcp_client.call_tool(name, arguments)
            except ToolExecutionError as e:
                return f"Error: {e}"

        while True:
            try:
                question = input("\n> ").strip()
            except EOFError:
                print()
                break
            if not question:
                continue

            try:
                result = await run_agent_loop(
                    question, chat_fn, tool_executor, system_prompt=system_prompt
                )
            except APIConnectionError:
                print(
                    f"Could not reach the model at {client.base_url} — "
                    "is `ollama serve` running, and have you run "
                    f"`ollama pull {model}`?"
                )
                continue
            except (AgentLoopError, ToolExecutionError) as e:
                print(f"error: {e}")
                continue

            for call in result.tool_calls:
                status = "error" if call.result.startswith("Error:") else "ok"
                summary = call.result if status == "error" else _truncate(call.result)
                print(f"  [tool:{status}] {call.name}({call.arguments}) -> {summary}")
            print(result.answer)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
