from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

registry = CollectorRegistry(auto_describe=True)

webhook_events_total = Counter(
    "webhook_events_total",
    "Total GitHub webhook events received",
    ["event"],
    registry=registry,
)

webhook_processing_seconds = Histogram(
    "webhook_processing_seconds",
    "Webhook processing duration in seconds",
    ["event"],
    registry=registry,
)

active_jobs = Gauge(
    "active_jobs",
    "Number of currently active agent jobs",
    registry=registry,
)

agent_runs_total = Counter(
    "agent_runs_total",
    "Total agent executions",
    ["agent", "status"],
    registry=registry,
)


def get_metrics_output() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
