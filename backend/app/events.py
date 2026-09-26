"""Best-effort Redis notifications for order WebSocket clients."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis import Redis
from redis import asyncio as redis_async
from redis.exceptions import RedisError

from .config import Settings

logger = logging.getLogger(__name__)
CHANNEL_PREFIX = "procurement:orders:"


def order_channel(order_id: int) -> str:
    return f"{CHANNEL_PREFIX}{order_id}"


def _event_payload(order_id: int, event: dict[str, Any]) -> str:
    return json.dumps({"order_id": order_id, **event}, default=str)


def publish_order_event(order_id: int, event: dict[str, Any], settings: Settings | None = None) -> None:
    """Publish after a committed worker transaction; notification failure never retries business work."""
    runtime_settings = settings or Settings()
    try:
        with Redis.from_url(runtime_settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2) as client:
            client.publish(order_channel(order_id), _event_payload(order_id, event))
    except RedisError:
        logger.warning("Unable to publish Redis notification for order %s", order_id)


async def publish_order_event_async(order_id: int, event: dict[str, Any], redis_url: str) -> bool:
    """Publish an API-originated event and report whether Redis accepted it."""
    client = redis_async.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.publish(order_channel(order_id), _event_payload(order_id, event))
        return True
    except RedisError:
        logger.warning("Unable to publish Redis notification for order %s", order_id)
        return False
    finally:
        await client.aclose()