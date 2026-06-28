from __future__ import annotations

from app.core.config import get_settings


def init_observability() -> None:
    """Initialize OpenTelemetry tracing. Plan 04 will fully implement.

    For now this is a no-op so the app can start.
    """
    settings = get_settings()
    # TODO(plan-04): Set up OTel TracerProvider, MeterProvider, auto-instrumentation
    _ = settings  # silence unused


def shutdown_observability() -> None:
    """Shutdown OTel providers (Plan 04)."""
    pass
