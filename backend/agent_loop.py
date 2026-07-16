"""The agentic tool-use loop that powers a single chat turn.

Design note: the client only ever sees plain {role, content} text turns —
all the tool_use / tool_result / server_tool_use bookkeeping for a turn stays
server-side and is discarded once the turn produces its final text. This
keeps the frontend trivial (append text, re-send the growing text history)
and keeps the server stateless between requests (no session store needed).
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic

from . import config
from .tools import CALCULATOR_TOOL_DEF, TOOL_DISPATCH

log = logging.getLogger("agent_loop")

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Server-side tool: Anthropic executes the search and returns results in the
# same response — there is no client dispatch for this one.
WEB_SEARCH_TOOL_DEF = {"type": "web_search_20260209", "name": "web_search"}

TOOLS = [CALCULATOR_TOOL_DEF, WEB_SEARCH_TOOL_DEF]

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a calculator tool and web "
    "search. Use web search for current or factual information you're not "
    "certain about; use the calculator for any nontrivial arithmetic rather "
    "than computing it yourself. Give clear, direct answers."
)

MAX_TOKENS = 4096
MAX_ITERATIONS = 20  # safety bound on client-tool round trips, not the primary control flow


class AgentError(Exception):
    """Raised when the loop can't produce a response (bad key, refusal, etc.)."""


def _history_to_messages(history: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [{"role": turn["role"], "content": turn["content"]} for turn in history]


def run_agent_turn(history: list[dict[str, str]]) -> str:
    """Run the tool-use loop for one turn and return the final assistant text.

    `history` is the full user-visible conversation so far, ending in the
    latest user message — plain {"role": ..., "content": ...} dicts.
    """
    messages = _history_to_messages(history)
    iterations = 0

    while True:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            log.warning("hit MAX_ITERATIONS (%d) without end_turn", MAX_ITERATIONS)
            raise AgentError("The assistant took too many steps to respond. Please try again.")

        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "refusal":
            raise AgentError("The assistant declined to answer that request.")

        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks).strip() or "(no response)"

        if response.stop_reason == "pause_turn":
            # Server-side tool (web_search) hit its internal round-trip cap.
            # Resend as-is — the API resumes where it left off. Do NOT add an
            # extra "continue" message; the trailing server_tool_use block is
            # the resume signal.
            messages.append({"role": "assistant", "content": response.content})
            continue

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                handler = TOOL_DISPATCH.get(block.name)
                if handler is None:
                    output = f"Error: no handler for tool '{block.name}'"
                    is_error = True
                else:
                    output = handler(block.input)
                    is_error = output.startswith("Error")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": is_error,
                    }
                )

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
                continue

            # tool_use with no client-side blocks to answer (shouldn't happen
            # given our tool set, but don't loop forever if it does).
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks).strip() or "(no response)"

        # max_tokens, stop_sequence, or anything unhandled — return what we have.
        log.warning("unhandled stop_reason: %s", response.stop_reason)
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks).strip() or "(response was cut off)"
