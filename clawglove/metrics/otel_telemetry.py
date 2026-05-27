"""
OpenTelemetry-backed telemetry.
Replaces custom JSONL telemetry with OTel spans and metrics.
Exports to any OTLP-compatible collector (Jaeger, Prometheus, Grafana, Datadog).
"""
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from clawglove.interfaces import TelemetryInterface

logger = logging.getLogger(__name__)


class OTelTelemetry(TelemetryInterface):
    """
    OpenTelemetry-backed telemetry.

    Four scalar metrics that matter for ClawGlove governance:
    - clawglove.events_per_second
    - clawglove.policy_violations_total
    - clawglove.replay_latency_ms
    - clawglove.tenant_isolation_breaches

    All other measurements attach as span attributes.
    """

    def __init__(self, otlp_endpoint: str = "http://localhost:4317", service_name: str = "clawglove"):
        # Tracer setup
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
        trace.set_tracer_provider(tracer_provider)
        self._tracer = trace.get_tracer(service_name)

        # Metrics setup
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=otlp_endpoint),
            export_interval_millis=5000,
        )
        meter_provider = MeterProvider(metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        meter = metrics.get_meter(service_name)

        # The four governance scalar metrics
        self._events_counter = meter.create_counter(
            "clawglove.events_total",
            description="Total events appended to the execution ledger",
        )
        self._violations_counter = meter.create_counter(
            "clawglove.policy_violations_total",
            description="Total policy violations detected and blocked",
        )
        self._isolation_breach_counter = meter.create_counter(
            "clawglove.tenant_isolation_breaches",
            description="Cross-tenant isolation breach attempts detected",
        )
        self._replay_latency = meter.create_histogram(
            "clawglove.replay_latency_ms",
            description="Replay operation latency in milliseconds",
            unit="ms",
        )

    def record_event(self, name: str, attributes: dict) -> None:
        """Record a named event as an OTel span."""
        with self._tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

            # Auto-increment governance counters based on event type
            if attributes.get("type") == "POLICY_VIOLATION":
                self._violations_counter.add(1, {"tenant_id": attributes.get("tenant_id", "unknown")})
            elif attributes.get("type") == "EVENT_APPEND":
                self._events_counter.add(1, {"tenant_id": attributes.get("tenant_id", "unknown")})
            elif attributes.get("type") == "ISOLATION_BREACH":
                self._isolation_breach_counter.add(1, {"tenant_id": attributes.get("tenant_id", "unknown")})

    def record_metric(self, name: str, value: float, attributes: dict) -> None:
        """Record a scalar metric. Maps replay latency to histogram."""
        if name == "replay_latency_ms":
            self._replay_latency.record(value, attributes)
        else:
            logger.debug("Unregistered metric: %s=%.2f attrs=%s", name, value, attributes)
