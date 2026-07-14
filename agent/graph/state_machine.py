"""LangGraph state machine: greet -> qualify_BANT -> handle_objection -> book_or_route -> close.

Defined jointly with P4 (Day 6). Every node reads/writes call state to Redis
so Ghost Mode and the dashboard reflect live progress.
"""

import logging

logger = logging.getLogger("agent.graph.state_machine")
