"""
arq worker — receives webhook events and dispatches to agent handlers.

Run with:
    arq workers.orchestrator.WorkerSettings
"""

from datetime import UTC, datetime

import structlog
from arq import cron
from arq.connections import RedisSettings

from agents.architecture import ArchitectureAgent
from agents.base import BaseAgent
from agents.deploy import DeployAgent
from agents.docs import DocsAgent
from agents.refactor import RefactorAgent
from agents.security import SecurityAgent
from agents.test_agent import TestAgent
from api.database import AsyncSessionLocal
from api.metrics import active_jobs, agent_runs_total, webhook_events_total
from api.models.job import Job, JobState

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Agent registry — maps event types to ordered list of agents
# ---------------------------------------------------------------------------

ALL_AGENTS: dict[str, list[BaseAgent]] = {
    "pull_request": [
        ArchitectureAgent(),
        SecurityAgent(),
        TestAgent(),
        RefactorAgent(),
        DocsAgent(),
    ],
    "push": [
        SecurityAgent(),
        DeployAgent(),
    ],
    "check_run": [],
    "installation": [],
    "installation_repositories": [],
}


async def _get_installation_id(payload: dict) -> int | None:
    return payload.get("installation", {}).get("id")


async def _update_job_state(
    job_id: int,
    state: JobState,
    *,
    error: str | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return
        job.state = state
        if started:
            job.attempts += 1
            job.started_at = now
        job.error_message = error
        if completed:
            job.completed_at = now
        await session.commit()


async def process_webhook_event(
    ctx: dict,
    *,
    event_type: str,
    delivery_id: str,
    payload: dict,
    db_job_id: int,
) -> dict:
    log = logger.bind(event=event_type, delivery=delivery_id, job_id=db_job_id)
    log.info("Processing webhook event")

    webhook_events_total.labels(event=event_type).inc()
    active_jobs.inc()

    await _update_job_state(db_job_id, JobState.RUNNING, started=True)

    installation_id = await _get_installation_id(payload)
    agents = ALL_AGENTS.get(event_type, [])
    results: dict[str, str] = {}

    try:
        for agent in agents:
            if not installation_id:
                log.warning("No installation_id in payload — skipping agent", agent=agent.name)
                results[agent.name] = "skipped_no_installation"
                continue

            log.info("Running agent", agent=agent.name)
            try:
                result = await agent.run(
                    event_type=event_type,
                    payload=payload,
                    installation_id=installation_id,
                )
                results[agent.name] = result.status.value
                agent_runs_total.labels(agent=agent.name, status=result.status.value).inc()
                log.info(
                    "Agent complete",
                    agent=agent.name,
                    status=result.status.value,
                    findings=len(result.findings),
                )
            except Exception as agent_exc:
                results[agent.name] = "error"
                agent_runs_total.labels(agent=agent.name, status="error").inc()
                log.error("Agent raised exception", agent=agent.name, error=str(agent_exc))

        await _update_job_state(db_job_id, JobState.COMPLETED, completed=True)
        log.info("All agents complete", results=results)
        return {"status": "completed", "agents": results}

    except Exception as exc:
        error_msg = str(exc)
        log.error("Orchestrator failed", error=error_msg)
        await _update_job_state(db_job_id, JobState.FAILED, error=error_msg, completed=True)
        agent_runs_total.labels(agent="orchestrator", status="failed").inc()
        raise

    finally:
        active_jobs.dec()


# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------


async def cleanup_old_jobs(ctx: dict) -> None:
    """Mark stale RUNNING jobs as FAILED (dead worker recovery)."""
    from datetime import timedelta

    from sqlalchemy import select

    threshold = datetime.now(UTC) - timedelta(hours=1)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.state == JobState.RUNNING).where(Job.started_at < threshold)
        )
        stale = result.scalars().all()
        for job in stale:
            job.state = JobState.FAILED
            job.error_message = "Timed out — worker likely crashed"
            job.completed_at = datetime.now(UTC)
        if stale:
            await session.commit()
            logger.warning("Stale jobs recovered", count=len(stale))


# ---------------------------------------------------------------------------
# arq WorkerSettings
# ---------------------------------------------------------------------------


def _get_redis_settings() -> RedisSettings:
    from workers.queue import _redis_settings

    return _redis_settings()


class WorkerSettings:
    functions = [process_webhook_event]
    cron_jobs = [cron(cleanup_old_jobs, minute={0, 30})]
    max_jobs = 10
    job_timeout = 300
    max_tries = 3
    retry_delay = 60
    keep_result = 3600
    queue_name = "default"

    @classmethod
    def redis_settings(cls) -> RedisSettings:
        return _get_redis_settings()
