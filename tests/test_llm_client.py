import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mcp import types

from agent.llm_client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    _to_wire_messages,
    build_chat_fn,
    build_client,
    mcp_tools_to_openai,
    model_name,
)


def test_model_name_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("OWA_MODEL", raising=False)
    assert model_name() == DEFAULT_MODEL


def test_model_name_respects_env_override(monkeypatch):
    monkeypatch.setenv("OWA_MODEL", "some-other-model")
    assert model_name() == "some-other-model"


def test_build_client_defaults_base_url_when_env_unset(monkeypatch):
    monkeypatch.delenv("OWA_LLM_BASE_URL", raising=False)
    client = build_client()
    assert str(client.base_url).rstrip("/") == DEFAULT_BASE_URL.rstrip("/")


def test_build_client_respects_env_override(monkeypatch):
    monkeypatch.setenv("OWA_LLM_BASE_URL", "http://example.com/v1")
    client = build_client()
    assert str(client.base_url).rstrip("/") == "http://example.com/v1"


def test_mcp_tools_to_openai_converts_shape():
    tools = [
        types.Tool(
            name="list_tables",
            description="List tables.",
            inputSchema={"type": "object", "properties": {}},
        )
    ]

    openai_tools = mcp_tools_to_openai(tools)

    assert openai_tools == [
        {
            "type": "function",
            "function": {
                "name": "list_tables",
                "description": "List tables.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_to_wire_messages_passes_through_messages_without_tool_calls():
    messages = [
        {"role": "system", "content": "you are an analyst"},
        {"role": "user", "content": "hi"},
    ]

    assert _to_wire_messages(messages) == messages


def test_to_wire_messages_reencodes_tool_calls():
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call_1", "name": "list_tables", "arguments": {"schema": "main"}}
            ],
        }
    ]

    wire_messages = _to_wire_messages(messages)

    assert wire_messages == [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "list_tables",
                        "arguments": json.dumps({"schema": "main"}),
                    },
                }
            ],
        }
    ]


def _fake_completion(*, content, tool_calls=()):
    message = SimpleNamespace(content=content, tool_calls=list(tool_calls))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


async def test_build_chat_fn_normalizes_response_with_no_tool_calls():
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=_fake_completion(content="the answer is 42"))
            )
        )
    )
    chat_fn = build_chat_fn(client, "some-model", tools=[])

    response = await chat_fn([{"role": "user", "content": "question"}])

    assert response == {"content": "the answer is 42", "tool_calls": []}


async def test_build_chat_fn_normalizes_response_with_tool_calls():
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="list_tables", arguments=json.dumps({"schema": "main"})),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=_fake_completion(content=None, tool_calls=[tool_call]))
            )
        )
    )
    chat_fn = build_chat_fn(client, "some-model", tools=[])

    response = await chat_fn([{"role": "user", "content": "how many tables?"}])

    assert response == {
        "content": None,
        "tool_calls": [
            {"id": "call_1", "name": "list_tables", "arguments": {"schema": "main"}}
        ],
    }
