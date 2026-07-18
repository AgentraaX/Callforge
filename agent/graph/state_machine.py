"""LangGraph state machine: greet -> qualify_BANT -> handle_objection -> book_or_route -> close.

Drafted jointly by P3 and P4 on Day 6. P4 owns the state definition and graph
structure; P3 wires it to the voice pipeline. Every node writes the current stage
to Redis so Ghost Mode and the dashboard reflect live progress.
"""
from typing import Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from agent.graph.nodes import (
    book_or_route,
    close,
    greet,
    handle_objection,
    qualify_bant,
)


class CallState(TypedDict):
    call_id: str
    stage: str                 # mirrors the node name currently executing
    transcript: list[dict]     # [{"speaker": "agent" | "prospect", "text": "..."}]
    budget_confirmed: bool
    authority_confirmed: bool
    need_confirmed: bool
    timeline_confirmed: bool
    objection_text: str | None
    outcome: str | None        # "booked" | "transferred" | "closed_lost" | None


def _route_qualify(state: CallState) -> Literal["handle_objection", "book_or_route"]:
    bant_complete = (
        state["budget_confirmed"]
        and state["authority_confirmed"]
        and state["need_confirmed"]
        and state["timeline_confirmed"]
    )
    return "book_or_route" if bant_complete else "handle_objection"


def _route_objection(state: CallState) -> Literal["qualify_bant", "book_or_route"]:
    bant_complete = (
        state["budget_confirmed"]
        and state["authority_confirmed"]
        and state["need_confirmed"]
        and state["timeline_confirmed"]
    )
    return "book_or_route" if bant_complete else "qualify_bant"


def build_graph() -> StateGraph:
    graph = StateGraph(CallState)

    graph.add_node("greet", greet)
    graph.add_node("qualify_bant", qualify_bant)
    graph.add_node("handle_objection", handle_objection)
    graph.add_node("book_or_route", book_or_route)
    graph.add_node("close", close)

    graph.add_edge(START, "greet")
    graph.add_edge("greet", "qualify_bant")
    graph.add_conditional_edges("qualify_bant", _route_qualify)
    graph.add_conditional_edges("handle_objection", _route_objection)
    graph.add_edge("book_or_route", "close")
    graph.add_edge("close", END)

    return graph


compiled_graph = build_graph().compile()
