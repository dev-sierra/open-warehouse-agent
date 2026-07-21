"""The tool-calling agent loop.

Deliberately decoupled from both the OpenAI SDK and the MCP client: it
takes plain async callables so it can be unit-tested with fakes, with no
real Ollama server or mcp_server subprocess involved. See
agent/llm_client.py and agent/mcp_client.py for the real implementations
that get wired in at the CLI layer (agent/cli.py).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

DEFAULT_SYSTEM_PROMPT = (
    "You are a data analyst answering questions about a company's orders "
    "and payment settlements. Use the list_tables, describe_table, and "
    "run_query tools to inspect the warehouse before answering questions "
    "about that data. Only answer a data question once you have queried "
    "the data — do not guess at numbers. Never write a sentence describing "
    "what you're about to look up (e.g. 'I will query...', 'Let's first "
    "check...') without actually calling the tool in that same turn — if "
    "you need data, call the tool immediately instead of narrating your "
    "intent to call it. If a question uses a business term that doesn't "
    "obviously match a table or column you already know about (e.g. "
    "'sales' when you haven't yet seen the schema), that is a reason to "
    "call list_tables immediately to resolve the ambiguity — it is free "
    "and safe — not a reason to hesitate or ask the user to clarify first. "
    "If the user's message isn't a "
    "question about the warehouse data — a greeting, small talk, or a "
    "question about who/what you are — just answer it directly and "
    "briefly in plain language. Do not call any tools for those, and do "
    "not turn them into an excuse to report statistics about the data. "
    "Always respond in English, regardless of what language is used "
    "elsewhere. When a question asks for an aggregate, a comparison, or "
    "anything you'd otherwise have to eyeball from a list of rows (counts, "
    "totals, gaps, outliers, 'is X missing'), write SQL that computes that "
    "result directly — such as using generate_series for a calendar and "
    "anti-joining against it to find missing dates — rather than dumping "
    "raw rows back and asking the user to work it out."
)

MAX_ITERATIONS = 12

EMPTY_RESPONSE_RETRY_MESSAGE = (
    "Your last response was empty. If you need data to answer, call a "
    "tool now. If you can answer directly, write out the answer."
)


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict
    result: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class AgentLoopError(RuntimeError):
    """Raised when the loop exhausts its iteration budget without an answer."""


# A normalized chat response: {"content": str | None, "tool_calls": [
#   {"id": str, "name": str, "arguments": dict}, ...
# ]}
ChatFn = Callable[[list[dict]], Awaitable[dict]]
ToolExecutorFn = Callable[[str, dict], Awaitable[str]]


async def run_agent_loop(
    question: str,
    chat_fn: ChatFn,
    tool_executor: ToolExecutorFn,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentResult:
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    tool_calls_made: list[ToolCallRecord] = []
    already_retried_empty = False

    for _ in range(max_iterations):
        response = await chat_fn(messages)
        tool_calls = response.get("tool_calls") or []
        content = response.get("content") or ""

        if not tool_calls:
            # Trust the model's own judgment on whether an answer needs a
            # tool call — the system prompt already instructs it to query
            # before answering data questions and to answer directly
            # otherwise. An earlier version of this loop force-nudged any
            # response with no tool_calls, on the theory that small models
            # sometimes narrate a plan instead of acting. In practice that
            # nudge couldn't distinguish "correctly decided no tool is
            # needed" from "stalling" — both look identical here — and it
            # would override already-correct direct answers, provoking a
            # confused, malformed second turn. Better to accept a no-op
            # answer at face value than to second-guess it in code.
            #
            # The one exception: a completely empty response is never a
            # legitimate answer to anything, tool needed or not — so
            # retrying that case (once) can't override a genuinely correct
            # answer the way the old blanket nudge did.
            if not content.strip() and not already_retried_empty:
                already_retried_empty = True
                messages.append({"role": "user", "content": EMPTY_RESPONSE_RETRY_MESSAGE})
                continue
            return AgentResult(answer=content, tool_calls=tool_calls_made)

        messages.append(
            {
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": tool_calls,
            }
        )
        for call in tool_calls:
            result = await tool_executor(call["name"], call["arguments"])
            tool_calls_made.append(
                ToolCallRecord(name=call["name"], arguments=call["arguments"], result=result)
            )
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": result}
            )

    raise AgentLoopError(f"exceeded {max_iterations} iterations without a final answer")
