"""
Queue helpers — thin wrapper around arq to enqueue orchestrator jobs.
"""
import json
import structlog
from arq import create_pool
from arq.connections import RedisSettings

from api.config import get_settings

logger = structlog.get_logger(__name__)

_pool = None


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    # arq takes host/port/db separately
    url = settings.redis_url  # redis://host:port/db
    parts = url.replace("redis://", "").split("/")
    host_port = parts[0].split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    return RedisSettings(host=host, port=port, database=db)


async def get_queue():
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    return _pool


async def enqueue_webhook_event(
    event_type: str,
    delivery_id: str,
    payload: dict,
    job_id: int,
) -> str:
    """Enqueue a webhook event for the orchestrator to process."""
    queue = await get_queue()
    job = await queue.enqueue_job(
        "process_webhook_event",
        event_type=event_type,
        delivery_id=delivery_id,
        payload=payload,
        db_job_id=job_id,
        _job_id=f"webhook:{delivery_id}",
        _queue_name="default",
    )
    logger.info(
        "Job enqueued",
        arq_job_id=job.job_id if job else None,
        event=event_type,
        delivery=delivery_id,
    )
    return job.job_id if job else ""


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
