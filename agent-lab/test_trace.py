"""Trace events from the agent loop. No API, no Ollama: the only tool used is local."""
import asyncio

from ollama import Message

import agent


class FakeResponse:
    """Looks like ollama's ChatResponse: a message plus token counts and durations (ns)."""
    def __init__(self, message, prompt_tokens, output_tokens, prompt_ns, output_ns, load_ns=0):
        self.message = message
        self.prompt_eval_count = prompt_tokens
        self.eval_count = output_tokens
        self.prompt_eval_duration = prompt_ns
        self.eval_duration = output_ns
        self.load_duration = load_ns


def test_model_calls_are_traced(monkeypatch):
    responses = days_between_then_answer()
    monkeypatch.setattr(agent.ollama, "chat", lambda **kwargs: next(responses))

    events = []
    messages = agent.new_conversation() + [{"role": "user", "content": "Days in January 2026?"}]
    asyncio.run(agent.run_agent_async(messages, agent.direct_toolbox(), trace=events.append))

    calls = [e for e in events if e["type"] == "model_call"]
    assert len(calls) == 2

    first, second = calls
    assert first["step"] == 1
    assert first["prompt_tokens"] == 400
    assert first["output_tokens"] == 20
    assert first["output_seconds"] == 0.5
    assert first["tool_calls"] == 1

    assert second["step"] == 2
    assert second["output_tokens"] == 5
    assert second["tool_calls"] == 0

def days_between_then_answer():
    """Test that the agent can call days_between and then answer the question."""
    return iter([
        # First call: the model asks for days_between
        FakeResponse(
            Message(role="assistant", tool_calls=[Message.ToolCall(function=Message.ToolCall.Function(
                name="days_between", arguments={"start": "2026-01-01", "end": "2026-01-31"}))]),
            prompt_tokens=400, output_tokens=20, prompt_ns=200_000_000, output_ns=500_000_000),
        FakeResponse(Message(role="assistant", content="30 days."),
                     prompt_tokens=450, output_tokens=5, prompt_ns=100_000_000, output_ns=250_000_000),
    ])

