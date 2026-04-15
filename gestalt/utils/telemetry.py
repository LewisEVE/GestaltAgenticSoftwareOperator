"""OpenTelemetry bootstrap helpers for the Gestalt runtime."""

from __future__ import annotations

from contextlib import suppress

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from gestalt.config import TelemetryConfig


def configure_tracing(config: TelemetryConfig) -> None:
    """Initialize OpenTelemetry tracing if enabled."""

    resource = Resource.create(
        {
            "service.name": config.service_name,
            **config.resource_attributes,
        },
    )
    provider = TracerProvider(resource=resource)
    if config.enabled and config.exporter_endpoint:
        exporter = OTLPSpanExporter(endpoint=config.exporter_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def shutdown_tracing() -> None:
    """Flush and shut down tracing gracefully."""

    provider = trace.get_tracer_provider()
    with suppress(Exception):
        provider.shutdown()  # type: ignore[attr-defined]
