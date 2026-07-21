import pytest

from agent.loop import AgentLoopError, run_agent_loop


def _fixed_chat_fn(*responses):
    responses = iter(responses)

    async def chat_fn(messages):
        return next(responses)

    return chat_fn


async def _fake_tool_executor(name, arguments):
    return f"result-for-{name}"


async def test_answer_after_at_least_one_tool_call_is_accepted():
    chat_fn = _fixed_chat_fn(
        {
            "content": None,
            "tool_calls": [{"id": "call_1", "name": "list_tables", "arguments": {}}],
        },
        {"content": "the answer is 42", "tool_calls": []},
    )

    result = await run_agent_loop("question", chat_fn, _fake_tool_executor)

    assert result.answer == "the answer is 42"
    assert len(result.tool_calls) == 1


async def test_question_needing_no_tool_is_answered_directly():
    # Regression test: the loop must not second-guess or force a tool call
    # onto a response that has none — an earlier version tried nudging any
    # no-tool-call response once, on the theory that small models sometimes
    # narrate a plan instead of acting. That couldn't distinguish "correctly
    # decided no tool is needed" (this case) from "stalling", and ended up
    # overriding already-correct direct answers. The loop now trusts the
    # model's own judgment, which the system prompt already guides.
    chat_fn = _fixed_chat_fn({"content": "Hello there!", "tool_calls": []})

    result = await run_agent_loop("hi", chat_fn, _fake_tool_executor)

    assert result.answer == "Hello there!"
    assert result.tool_calls == []


async def test_empty_response_is_retried_once_then_tool_call_accepted():
    # Regression test: qwen2.5:7b-instruct sometimes returns a completely
    # empty response (no content, no tool_calls) on ambiguous questions
    # instead of exploring the schema. Unlike the old blanket nudge, this
    # is safe to retry unconditionally — an empty response is never a
    # legitimate answer, so retrying it can't override a correct one.
    chat_fn = _fixed_chat_fn(
        {"content": "", "tool_calls": []},
        {
            "content": None,
            "tool_calls": [{"id": "call_1", "name": "list_tables", "arguments": {}}],
        },
        {"content": "the answer is 42", "tool_calls": []},
    )

    result = await run_agent_loop("question", chat_fn, _fake_tool_executor)

    assert result.answer == "the answer is 42"
    assert len(result.tool_calls) == 1


async def test_empty_response_retried_once_then_accepted_even_if_still_empty():
    chat_fn = _fixed_chat_fn(
        {"content": "", "tool_calls": []},
        {"content": "", "tool_calls": []},
    )

    result = await run_agent_loop("question", chat_fn, _fake_tool_executor)

    assert result.answer == ""
    assert result.tool_calls == []


async def test_single_tool_call_then_answer():
    chat_fn = _fixed_chat_fn(
        {
            "content": None,
            "tool_calls": [{"id": "call_1", "name": "list_tables", "arguments": {}}],
        },
        {"content": "there are 3 tables", "tool_calls": []},
    )

    result = await run_agent_loop("question", chat_fn, _fake_tool_executor)

    assert result.answer == "there are 3 tables"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "list_tables"
    assert result.tool_calls[0].result == "result-for-list_tables"


async def test_multiple_rounds_of_tool_calls():
    chat_fn = _fixed_chat_fn(
        {
            "content": None,
            "tool_calls": [{"id": "call_1", "name": "list_tables", "arguments": {}}],
        },
        {
            "content": None,
            "tool_calls": [
                {"id": "call_2", "name": "run_query", "arguments": {"sql": "select 1"}}
            ],
        },
        {"content": "final answer", "tool_calls": []},
    )

    result = await run_agent_loop("question", chat_fn, _fake_tool_executor)

    assert result.answer == "final answer"
    assert [c.name for c in result.tool_calls] == ["list_tables", "run_query"]


async def test_exceeding_max_iterations_raises():
    async def always_calls_tool(messages):
        return {
            "content": None,
            "tool_calls": [{"id": "call_1", "name": "list_tables", "arguments": {}}],
        }

    with pytest.raises(AgentLoopError):
        await run_agent_loop(
            "question", always_calls_tool, _fake_tool_executor, max_iterations=2
        )
