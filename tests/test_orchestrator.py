from unittest.mock import AsyncMock, patch

import pytest

from workers.orchestrator import ALL_AGENTS, process_webhook_event


@pytest.fixture(autouse=True)
def patch_db():
    with patch("workers.orchestrator.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=None)
        mock_session_cls.return_value = mock_session
        yield mock_session


@pytest.mark.anyio
async def test_process_pull_request_dispatches_agents(patch_db):
    ctx = {}
    result = await process_webhook_event(
        ctx,
        event_type="pull_request",
        delivery_id="test-delivery-123",
        payload={"action": "opened"},
        db_job_id=1,
    )
    assert result["status"] == "completed"
    for agent in ALL_AGENTS["pull_request"]:
        assert agent.name in result["agents"]


@pytest.mark.anyio
async def test_process_unknown_event_completes_with_no_agents(patch_db):
    ctx = {}
    result = await process_webhook_event(
        ctx,
        event_type="unknown_event",
        delivery_id="test-delivery-456",
        payload={},
        db_job_id=2,
    )
    assert result["status"] == "completed"
    assert result["agents"] == {}


@pytest.mark.anyio
async def test_agent_dispatch_map_covers_main_events():
    assert "pull_request" in ALL_AGENTS
    assert "push" in ALL_AGENTS
    assert len(ALL_AGENTS["pull_request"]) > 0
    # Verify agent names are valid strings
    for agent in ALL_AGENTS["pull_request"]:
        assert isinstance(agent.name, str)
