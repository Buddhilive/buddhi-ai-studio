from __future__ import annotations

import json

from app.services.agent.events import AgentEventEmitter


async def _collect(emitter: AgentEventEmitter) -> list[dict]:
    out: list[dict] = []
    async for raw in emitter.stream():
        if raw == "data: [DONE]\n\n":
            break
        if raw.startswith("data: "):
            out.append(json.loads(raw[6:]))
    return out


async def test_nested_span_hierarchy_for_egm_harness_and_rlm():
    emitter = AgentEventEmitter("run_spans_01")

    async with emitter.span("egm_review_r1"):
        async with emitter.span("egm_zoom_out_r1_s1"):
            await emitter.emit_egm_reviewer_status("Stage 1", "zoom_out", "completed", round_num=1, findings_count=2)

    async with emitter.span("harness_cal_1"):
        async with emitter.span("probe_cand_a"):
            await emitter.emit_harness_probe(1, "cand_a", "passed", 2, 0, 1.0, 150)

    async with emitter.span("rlm_repl_1"):
        async with emitter.span("rlm_req_42"):
            await emitter.emit_text_delta("rlm", "snippet answer")

    await emitter.emit_run_end("completed")
    events = await _collect(emitter)

    assert events[0]["span_id"] == "egm_zoom_out_r1_s1"
    assert events[0]["parent_span_id"] == "egm_review_r1"

    assert events[1]["span_id"] == "probe_cand_a"
    assert events[1]["parent_span_id"] == "harness_cal_1"

    assert events[2]["span_id"] == "rlm_req_42"
    assert events[2]["parent_span_id"] == "rlm_repl_1"
