from __future__ import annotations

import asyncio
import json

from app.services.agent.events import AgentEventEmitter


async def _drain_emitter(emitter: AgentEventEmitter) -> list[dict]:
    events: list[dict] = []
    async for raw in emitter.stream():
        if raw == "data: [DONE]\n\n":
            break
        if raw.startswith("data: "):
            events.append(json.loads(raw[6:]))
    return events


async def test_monotonic_seq_and_tool_args_delta():
    emitter = AgentEventEmitter("run_test_seq_01")
    await emitter.emit_run_start({"model": "gemma-4-e4b"})
    await emitter.emit_turn_start("turn_1", node="reason", turn_index=1, prompt_preview="Fix bug")
    await emitter.emit_reasoning_delta("reason", "Checking ")
    await emitter.emit_tool_args_delta("tc_1", "run_command", '{"command": "pytest"}', node="act")
    await emitter.emit_tool_call("tc_1", "run_command", {"command": "pytest"})
    await emitter.emit_turn_end("turn_1", node="reason", duration_ms=42)
    await emitter.emit_run_end("completed", steps=1)

    events = await _drain_emitter(emitter)
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, len(events) + 1))
    assert all(e["timestamp_ms"] > 0 for e in events)
    assert events[2]["turn_id"] == "turn_1"
    assert events[3]["event"] == "tool.args.delta"
    assert events[3]["data"]["tool_call_id"] == "tc_1"


async def test_concurrent_runs_have_isolated_seq_and_spans():
    e1 = AgentEventEmitter("run_iso_1")
    e2 = AgentEventEmitter("run_iso_2")

    async def worker(emitter: AgentEventEmitter, label: str):
        async with emitter.span(f"span_{label}", parent_span_id="root"):
            await emitter.emit_text_delta("reason", label)
            await emitter.emit_run_end("completed")

    await asyncio.gather(worker(e1, "a"), worker(e2, "b"))
    ev1 = await _drain_emitter(e1)
    ev2 = await _drain_emitter(e2)

    assert [e["seq"] for e in ev1] == [1, 2]
    assert [e["seq"] for e in ev2] == [1, 2]
    assert ev1[0]["span_id"] == "span_a"
    assert ev1[0]["parent_span_id"] == "root"
    assert ev2[0]["span_id"] == "span_b"


async def test_redaction_and_backpressure_preserves_lifecycle_events():
    emitter = AgentEventEmitter("run_pressure_01")
    await emitter.emit_tool_call("tc_sec", "run_command", {"command": "echo Bearer sk-abcdefghijklmnopqrst"})
    first_raw = await emitter._queue.get()
    dumped = json.dumps(first_raw.data)
    assert "[REDACTED" in dumped
    assert "sk-abcdefghijklmnopqrst" not in dumped

    # Fill queue with tool.output.delta beyond capacity; lifecycle run.end must still be delivered
    for i in range(600):
        await emitter.emit_tool_output_delta("tc_sec", "run_command", "stdout", f"line {i}\n", chunk_index=i)
    await emitter.emit_run_end("completed")

    events = await _drain_emitter(emitter)
    assert emitter.dropped_deltas > 0
    assert events[-1]["event"] == "run.end"
