from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

import api.models  # noqa: F401 — registers all SQLAlchemy models
from api.cache import close_redis, get_redis_client
from api.config import get_settings
from api.logging_config import configure_logging
from api.metrics import get_metrics_output
from api.routers import projects, webhook
from api.telemetry import configure_telemetry, instrument_app

settings = get_settings()
configure_logging(settings)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GitHub AI DevOps Agent", env=settings.app_env, version="0.1.0")
    configure_telemetry(
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        enabled=settings.otel_enabled,
    )
    redis = get_redis_client()
    await redis.ping()
    logger.info("Redis connected")
    yield
    logger.info("Shutting down")
    await close_redis()


app = FastAPI(
    title="GitHub AI DevOps Agent",
    description="Multi-tenant SaaS platform for AI-powered DevOps automation",
    version="0.1.0",
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

instrument_app(app)

app.include_router(webhook.router)
app.include_router(projects.router)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env, "version": "0.1.0"}


@app.get("/metrics", tags=["ops"])
async def metrics() -> Response:
    data, content_type = get_metrics_output()
    return Response(content=data, media_type=content_type)
