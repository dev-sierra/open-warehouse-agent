"""OpenAI-compatible LLM client, wired against a local Ollama server.

Deliberately built on the `openai` SDK talking to a locally overridden
base_url rather than a bespoke Ollama client: Ollama (and later, the
Phase 3 AWS gateway) exposes the same OpenAI-compatible chat-completions
API, so this module — and every request it makes — never leaves
localhost/your own infrastructure. No OpenAI account is used; pointing at
the gateway instead of Ollama is just OWA_LLM_BASE_URL (plus
OWA_LLM_API_KEY, to satisfy the gateway's bearer-token check) — no code
change here.
"""

from __future__ import annotations

import json
import os

from mcp import types
from openai import AsyncOpenAI

DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_BASE_URL = "http://localhost:11434/v1"


def build_client() -> AsyncOpenAI:
    base_url = os.environ.get("OWA_LLM_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("OWA_LLM_API_KEY", "ollama")
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def model_name() -> str:
    return os.environ.get("OWA_MODEL", DEFAULT_MODEL)


def mcp_tools_to_openai(tools: list[types.Tool]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools
    ]


def _to_wire_messages(messages: list[dict]) -> list[dict]:
    """Re-encode agent/loop.py's normalized tool_calls into OpenAI wire format.

    run_agent_loop stores tool_calls as the same {"id","name","arguments"}
    shape chat_fn returns them in (see ChatFn in agent/loop.py) so the loop
    stays decoupled from any particular wire protocol. This client is the
    one place that has to translate back before replaying history to the
    API — the wire format needs "type": "function" and a JSON-*string*
    arguments field, not a dict.
    """
    wire_messages = []
    for message in messages:
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            wire_messages.append(message)
            continue
        wire_messages.append(
            {
                **message,
                "tool_calls": [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"]),
                        },
                    }
                    for call in tool_calls
                ],
            }
        )
    return wire_messages


def build_chat_fn(client: AsyncOpenAI, model: str, tools: list[dict]):
    """Returns a ChatFn (see agent/loop.py) bound to this client/model/tools."""

    async def chat_fn(messages: list[dict]) -> dict:
        completion = await client.chat.completions.create(
            model=model,
            messages=_to_wire_messages(messages),
            tools=tools or None,
            temperature=0,
        )
        message = completion.choices[0].message
        return {
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": json.loads(call.function.arguments or "{}"),
                }
                for call in (message.tool_calls or [])
            ],
        }

    return chat_fn
