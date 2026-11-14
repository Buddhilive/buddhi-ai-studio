from __future__ import annotations

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agent.egm.nodes import (
    brainstorm_node,
    draft_node,
    drift_report_node,
    goldfish_review_node,
    goldfish_verify_node,
    resolve_node,
)
from app.services.agent.nodes import (
    act_node,
    analyze_node,
    observe_node,
    plan_node,
    review_node,
    rlm_run_node,
)
from app.services.agent.routing import (
    route_after_act,
    route_after_analyze,
    route_after_goldfish_verify,
    route_after_observe,
    route_after_resolve,
    route_after_review,
)
from app.services.agent.state import AgentState


def _wrap_node(node_fn: Any):
    async def _wrapped(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        emitter = None
        if config and "configurable" in config:
            emitter = config["configurable"].get("emitter")
        return await node_fn(state, emitter=emitter)
    return _wrapped


def build_agent_graph(checkpointer: Any | None = None, interrupt_before: list[str] | None = None):
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("analyze", _wrap_node(analyze_node))
    builder.add_node("plan", _wrap_node(plan_node))
    builder.add_node("act", _wrap_node(act_node))
    builder.add_node("observe", _wrap_node(observe_node))
    builder.add_node("review", _wrap_node(review_node))
    builder.add_node("rlm_run", _wrap_node(rlm_run_node))

    # EGM nodes
    builder.add_node("brainstorm", _wrap_node(brainstorm_node))
    builder.add_node("draft", _wrap_node(draft_node))
    builder.add_node("goldfish_review", _wrap_node(goldfish_review_node))
    builder.add_node("resolve", _wrap_node(resolve_node))
    builder.add_node("goldfish_verify", _wrap_node(goldfish_verify_node))
    builder.add_node("drift_report", _wrap_node(drift_report_node))

    # Entry edge
    builder.add_edge(START, "analyze")

    # Conditional transitions from analyze
    builder.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {
            "plan": "plan",
            "rlm_run": "rlm_run",
            "draft": "draft",
            "brainstorm": "brainstorm",
            "drift_report": "drift_report",
            "end": END,
        },
    )

    builder.add_edge("rlm_run", END)
    builder.add_edge("drift_report", END)
    builder.add_edge("brainstorm", "draft")
    builder.add_edge("draft", "goldfish_review")
    builder.add_edge("goldfish_review", "resolve")

    builder.add_conditional_edges(
        "resolve",
        route_after_resolve,
        {"plan": "plan", "draft": "draft", "goldfish_review": "goldfish_review", "end": END},
    )

    builder.add_edge("plan", "act")

    builder.add_conditional_edges(
        "act",
        route_after_act,
        {"observe": "observe", "review": "review", "goldfish_verify": "goldfish_verify", "end": END},
    )

    builder.add_conditional_edges(
        "observe",
        route_after_observe,
        {"review": "review", "goldfish_verify": "goldfish_verify", "end": END},
    )

    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"plan": "plan", "act": "act", "end": END},
    )

    builder.add_conditional_edges(
        "goldfish_verify",
        route_after_goldfish_verify,
        {"plan": "plan", "act": "act", "end": END},
    )

    return builder.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


# Precompiled singleton graph with checkpointer and resolve interrupt gate
from app.services.agent.checkpointer import agent_checkpointer

agent_graph = build_agent_graph(
    checkpointer=agent_checkpointer,
    interrupt_before=["resolve"],
)
