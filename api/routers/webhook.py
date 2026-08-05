import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.job import Job, JobState

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["github"])

settings = get_settings()

# Events that trigger agent processing
PROCESSABLE_EVENTS = {
    "pull_request",
    "push",
    "check_run",
    "installation",
    "installation_repositories",
}


def _verify_signature(payload: bytes, signature_header: str | None) -> None:
    if not settings.github_webhook_secret:
        logger.warning("Webhook secret not configured — skipping signature check")
        return
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Hub-Signature-256 header"
        )
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature format"
        )

    expected = hmac.new(
        settings.github_webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")

    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature mismatch")


@router.post("")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> JSONResponse:
    payload_bytes = await request.body()
    _verify_signature(payload_bytes, x_hub_signature_256)

    event = x_github_event or "unknown"
    delivery = x_github_delivery or "unknown"
    payload_dict = json.loads(payload_bytes) if payload_bytes else {}

    repo_full_name = (
        payload_dict.get("repository", {}).get("full_name")
        if isinstance(payload_dict, dict)
        else None
    )

    logger.info("Webhook received", event_type=event, delivery=delivery, repo=repo_full_name)

    if event not in PROCESSABLE_EVENTS:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ignored", "event": event, "reason": "not a processable event"},
        )

    # Persist job record
    job = Job(
        event_type=event,
        delivery_id=delivery,
        repository_full_name=repo_full_name,
        payload=payload_bytes.decode(),
        state=JobState.PENDING,
        max_attempts=3,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue for async processing
    try:
        from workers.queue import enqueue_webhook_event

        arq_id = await enqueue_webhook_event(
            event_type=event,
            delivery_id=delivery,
            payload=payload_dict,
            job_id=job.id,
        )
        job.arq_job_id = arq_id
        await db.commit()
    except Exception as exc:
        logger.error("Failed to enqueue job", error=str(exc), job_id=job.id)
        # Job stays in PENDING — cleanup cron will handle it

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "accepted", "event": event, "delivery": delivery, "job_id": job.id},
    )
