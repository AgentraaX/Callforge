"""Function-calling tools exposed to the LLM: book_meeting, transfer_to_human, log_objection."""

import logging

logger = logging.getLogger("agent.graph.tools")


async def book_meeting(**kwargs):
    raise NotImplementedError


async def transfer_to_human(**kwargs):
    raise NotImplementedError


async def log_objection(**kwargs):
    raise NotImplementedError
