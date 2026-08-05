import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

WEBHOOK_SECRET = "test-secret"
PAYLOAD = json.dumps({"action": "opened", "number": 1}).encode()


def _sign(payload: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _mock_db_session():
    mock_db = AsyncMock()

    async def fake_refresh(obj):
        obj.id = 42
        obj.arq_job_id = None

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=fake_refresh)
    mock_db.add = MagicMock()
    return mock_db


@pytest.fixture(autouse=True)
def patch_infra():
    with (
        patch("api.cache.get_redis_client") as mock_redis_factory,
        patch("api.telemetry.configure_telemetry"),
        patch("api.telemetry.instrument_app"),
        patch("workers.queue.enqueue_webhook_event", new_callable=AsyncMock, return_value="arq-123"),
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis_factory.return_value = mock_redis
        yield


@pytest.fixture
def override_secret(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(override_secret):
    from api.config import get_settings

    get_settings.cache_clear()

    from api.database import get_db
    from api.main import app

    app.dependency_overrides[get_db] = _mock_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=PAYLOAD,
            headers={
                "X-Hub-Signature-256": _sign(PAYLOAD, WEBHOOK_SECRET),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "abc-123",
                "Content-Type": "application/json",
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 202
    assert response.json()["event"] == "pull_request"


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(override_secret):
    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=PAYLOAD,
            headers={
                "X-Hub-Signature-256": "sha256=badhash",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(override_secret):
    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=PAYLOAD,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_ignores_non_processable_events(override_secret):
    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=PAYLOAD,
            headers={
                "X-Hub-Signature-256": _sign(PAYLOAD, WEBHOOK_SECRET),
                "X-GitHub-Event": "star",
                "X-GitHub-Delivery": "xyz-999",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
