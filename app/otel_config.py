"""
OpenTelemetry configuration and setup for Insights Host Inventory.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.propagators.tracecontext import TraceContextPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from app.logging import get_logger

logger = get_logger(__name__)


class OpenTelemetryConfig:
    """OpenTelemetry configuration for the inventory service."""

    def __init__(self):
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "insights-host-inventory")
        self.service_version = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
        self.environment = os.getenv("OTEL_ENVIRONMENT", "development")

        # Exporter configuration
        self.otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
        self.jaeger_endpoint = os.getenv("OTEL_JAEGER_ENDPOINT")
        self.otlp_endpoint = os.getenv("OTEL_OTLP_ENDPOINT")
        self.console_exporter = os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true"

        # Sampling configuration
        self.trace_sample_rate = float(os.getenv("OTEL_TRACE_SAMPLE_RATE", "0.1"))

        # Instrumentation configuration
        self.instrument_flask = os.getenv("OTEL_INSTRUMENT_FLASK", "true").lower() == "true"
        self.instrument_sqlalchemy = os.getenv("OTEL_INSTRUMENT_SQLALCHEMY", "true").lower() == "true"
        self.instrument_kafka = os.getenv("OTEL_INSTRUMENT_KAFKA", "true").lower() == "true"
        self.instrument_psycopg2 = os.getenv("OTEL_INSTRUMENT_PSYCOPG2", "true").lower() == "true"

        # Custom attributes
        self.custom_attributes = self._parse_custom_attributes()

    def _parse_custom_attributes(self) -> dict[str, str]:
        """Parse custom attributes from environment variables."""
        attributes = {}
        custom_attrs = os.getenv("OTEL_CUSTOM_ATTRIBUTES", "")
        if custom_attrs:
            try:
                for attr in custom_attrs.split(","):
                    key, value = attr.strip().split("=", 1)
                    attributes[key] = value
            except ValueError as e:
                logger.warning("Failed to parse OTEL_CUSTOM_ATTRIBUTES: %s", e)
        return attributes

    def setup_tracing(self) -> trace.Tracer | None:
        """Set up OpenTelemetry tracing with configured exporters."""
        if not self.otel_enabled:
            logger.info("OpenTelemetry is disabled")
            return None

        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.version": self.service_version,
                "deployment.environment": self.environment,
                **self.custom_attributes,
            }
        )

        # Set up tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Set up exporters
        exporters = []

        if self.jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=self.jaeger_endpoint.split(":")[0]
                if ":" in self.jaeger_endpoint
                else self.jaeger_endpoint,
                agent_port=int(self.jaeger_endpoint.split(":")[1]) if ":" in self.jaeger_endpoint else 14268,
            )
            exporters.append(jaeger_exporter)
            logger.info("Configured Jaeger exporter: %s", self.jaeger_endpoint)

        if self.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
            exporters.append(otlp_exporter)
            logger.info("Configured OTLP exporter: %s", self.otlp_endpoint)

        if self.console_exporter:
            console_exporter = ConsoleSpanExporter()
            exporters.append(console_exporter)
            logger.info("Configured console exporter")

        if not exporters:
            logger.warning("No OpenTelemetry exporters configured")

        # Add span processors
        for exporter in exporters:
            span_processor = BatchSpanProcessor(exporter)
            tracer_provider.add_span_processor(span_processor)

        # Set up propagators
        propagators = [
            TraceContextPropagator(),
            B3MultiFormat(),
            JaegerPropagator(),
        ]
        set_global_textmap(CompositeHTTPPropagator(propagators))

        # Get tracer
        tracer = trace.get_tracer(__name__)
        logger.info("OpenTelemetry tracing initialized for service: %s", self.service_name)

        return tracer

    def instrument_libraries(self):
        """Instrument libraries with OpenTelemetry."""
        if not self.otel_enabled:
            return

        try:
            if self.instrument_flask:
                FlaskInstrumentor().instrument()
                logger.info("Flask instrumentation enabled")
        except Exception as e:
            logger.warning("Failed to instrument Flask: %s", e)

        try:
            if self.instrument_sqlalchemy:
                SQLAlchemyInstrumentor().instrument()
                logger.info("SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.warning("Failed to instrument SQLAlchemy: %s", e)

        try:
            if self.instrument_kafka:
                KafkaInstrumentor().instrument()
                logger.info("Kafka instrumentation enabled")
        except Exception as e:
            logger.warning("Failed to instrument Kafka: %s", e)

        try:
            if self.instrument_psycopg2:
                Psycopg2Instrumentor().instrument()
                logger.info("Psycopg2 instrumentation enabled")
        except Exception as e:
            logger.warning("Failed to instrument Psycopg2: %s", e)


# Global configuration instance
_otel_config = None


def get_otel_config() -> OpenTelemetryConfig:
    """Get the global OpenTelemetry configuration instance."""
    global _otel_config
    if _otel_config is None:
        _otel_config = OpenTelemetryConfig()
    return _otel_config


def setup_opentelemetry() -> trace.Tracer | None:
    """Set up OpenTelemetry for the inventory service."""
    config = get_otel_config()
    tracer = config.setup_tracing()
    config.instrument_libraries()
    return tracer


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Get an OpenTelemetry tracer instance."""
    return trace.get_tracer(name)
