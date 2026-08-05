import structlog

logger = structlog.get_logger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry packages not available — tracing disabled")


def configure_telemetry(service_name: str, otlp_endpoint: str, enabled: bool) -> None:
    if not enabled or not _OTEL_AVAILABLE:
        logger.info("OpenTelemetry disabled")
        return

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OTLP exporter configured", endpoint=otlp_endpoint)
    except Exception as exc:
        logger.warning("OTLP exporter not available", error=str(exc))

    trace.set_tracer_provider(provider)
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()
    logger.info("OpenTelemetry configured", service=service_name)


def instrument_app(app) -> None:
    if not _OTEL_AVAILABLE:
        return
    FastAPIInstrumentor.instrument_app(app)
