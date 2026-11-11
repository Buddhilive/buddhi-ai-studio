from __future__ import annotations

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agent.nodes import (
    act_node,
    analyze_node,
    observe_node,
    plan_node,
    review_node,
)
from app.services.agent.routing import (
    route_after_act,
    route_after_analyze,
    route_after_observe,
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

    # Entry edge
    builder.add_edge(START, "analyze")

    # Conditional transitions
    builder.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {"plan": "plan", "end": END},
    )

    builder.add_edge("plan", "act")

    builder.add_conditional_edges(
        "act",
        route_after_act,
        {"observe": "observe", "review": "review", "end": END},
    )

    builder.add_conditional_edges(
        "observe",
        route_after_observe,
        {"review": "review", "end": END},
    )

    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"plan": "plan", "act": "act", "end": END},
    )

    return builder.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


# Precompiled singleton graph with checkpointer
from app.services.agent.checkpointer import agent_checkpointer
agent_graph = build_agent_graph(checkpointer=agent_checkpointer)
