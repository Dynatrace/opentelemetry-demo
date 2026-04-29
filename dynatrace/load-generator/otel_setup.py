#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import sys

from opentelemetry import trace
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger_provider = LoggerProvider(
    resource=Resource.create(
        {
            "service.name": "load-generator",
        }
    )
)
set_logger_provider(logger_provider)
_log_exporter = OTLPLogExporter(insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(_log_exporter))
_otlp_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

# Attach OTLP handler to root logger
logging.getLogger().addHandler(_otlp_handler)
logging.getLogger().setLevel(logging.INFO)

# Named logger with its own StreamHandler so our messages are visible in the
# terminal regardless of how Locust reconfigures the root logger after startup.
log = logging.getLogger("loadgen")
log.setLevel(logging.INFO)
log.propagate = False  # don't double-emit through root
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setLevel(logging.INFO)
_stream_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
)
log.addHandler(_stream_handler)
log.addHandler(_otlp_handler)  # also forward to OTLP

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
_metric_exporter = OTLPMetricExporter(insecure=True)
set_meter_provider(MeterProvider([PeriodicExportingMetricReader(_metric_exporter)]))

# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------
tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

# ---------------------------------------------------------------------------
# Instrumentors
# Instrumented manually to avoid errors with locust gevent monkey-patching.
# ---------------------------------------------------------------------------
Jinja2Instrumentor().instrument()
RequestsInstrumentor().instrument()
SystemMetricsInstrumentor().instrument()
URLLib3Instrumentor().instrument()
logging.info("Instrumentation complete")
