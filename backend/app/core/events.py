"""Event bus for decoupled, event-driven architecture.

Components publish events (e.g. "inference_completed") and subscribers
handle them asynchronously. This keeps the chat endpoint fast while
logging and analytics happen in the background.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Registry: event_name -> list of async handler functions
_subscribers: dict[str, list[Callable[..., Coroutine]]] = defaultdict(list)


def subscribe(event_name: str, handler: Callable[..., Coroutine]) -> None:
    """Register an async handler for a named event."""
    _subscribers[event_name].append(handler)
    logger.info("Subscribed %s to event '%s'", handler.__name__, event_name)


async def publish(event_name: str, payload: dict[str, Any]) -> None:
    """Fire all handlers for *event_name* concurrently.

    Errors in individual handlers are logged but do not propagate,
    so a failing subscriber never breaks the main request flow.
    """
    handlers = _subscribers.get(event_name, [])
    if not handlers:
        return

    tasks = [asyncio.create_task(_safe_call(h, payload)) for h in handlers]
    await asyncio.gather(*tasks)


async def _safe_call(handler: Callable, payload: dict) -> None:
    try:
        await handler(payload)
    except Exception:
        logger.exception("Event handler %s failed", handler.__name__)
