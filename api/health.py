"""
Extended health check with dependency status.
"""

from api.cache import get_redis_client


async def check_redis() -> dict:
    try:
        redis = get_redis_client()
        await redis.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def get_health_details() -> dict:
    redis_status = await check_redis()
    healthy = redis_status["status"] == "ok"
    return {
        "status": "ok" if healthy else "degraded",
        "dependencies": {
            "redis": redis_status,
        },
    }
