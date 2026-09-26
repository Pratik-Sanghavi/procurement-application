"""Redis Pub/Sub relay for FastAPI order WebSocket connections."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from redis import asyncio as redis_async
from redis.exceptions import RedisError

from .events import CHANNEL_PREFIX

logger = logging.getLogger(__name__)
Delivery = Callable[[int, dict[str, Any]], Awaitable[None]]


async def relay_order_events(redis_url: str, deliver: Delivery, stop: asyncio.Event) -> None:
    """Relay all order channels; reconnect until application shutdown."""
    while not stop.is_set():
        client = redis_async.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        try:
            async with client.pubsub() as pubsub:
                await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
                while not stop.is_set():
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message is None:
                        continue
                    try:
                        payload = json.loads(message["data"])
                        order_id = int(payload.pop("order_id"))
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                        logger.warning("Discarding malformed Redis order event")
                        continue
                    await deliver(order_id, payload)
        except RedisError:
            logger.warning("Redis order-event relay disconnected; retrying", exc_info=True)
        finally:
            await client.aclose()
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except TimeoutError:
            pass