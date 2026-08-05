import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def patch_infra():
    with patch("api.cache.get_redis_client") as mock_redis_factory, \
         patch("api.telemetry.configure_telemetry"), \
         patch("api.telemetry.instrument_app"):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis_factory.return_value = mock_redis
        yield


@pytest.mark.anyio
async def test_list_projects_empty_db():
    from sqlalchemy.ext.asyncio import AsyncSession
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from api.main import app
    from api.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/projects")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_get_project_not_found():
    from sqlalchemy.ext.asyncio import AsyncSession
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    from api.main import app
    from api.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/projects/999")

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.anyio
async def test_metrics_endpoint_returns_prometheus_format():
    from api.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
