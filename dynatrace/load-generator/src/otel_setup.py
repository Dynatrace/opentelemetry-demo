#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import sys

from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

# gRPC channel options applied to all three OTLP exporters (traces, metrics, logs).
#
# Root cause of VmData=835 MB / ~400 MB/h RSS growth:
# The gRPC C core manages its own C heap for write buffers, retry queues, and
# keepalive state.  With default settings it has no bound on pending write
# buffer size and retries indefinitely — when the OTel Collector is slow or
# the network hiccups, the C heap grows without limit, completely invisible to
# Python's tracemalloc.
#
# grpc.max_send_message_length / grpc.max_receive_message_length:
#   Cap individual message size to 4 MB (default is unlimited).
# grpc.keepalive_time_ms / grpc.keepalive_timeout_ms:
#   Send keepalive pings every 30 s; declare the connection dead after 10 s.
#   Without this, idle connections accumulate stale C-heap state.
# grpc.keepalive_permit_without_calls:
#   Allow keepalive pings even when there are no active RPCs.
# grpc.http2.max_pings_without_data:
#   0 = no limit (needed for keepalive to work reliably).
# grpc.enable_retries:
#   0 = disable automatic gRPC-level retries.  The OTel SDK already has its
#   own retry logic (BatchSpanProcessor / PeriodicExportingMetricReader back-
#   off).  gRPC retries on top of that double-buffer every failed export in
#   the C heap, which is the primary source of unbounded VmData growth.
_GRPC_CHANNEL_OPTIONS = (
    ("grpc.max_send_message_length", 4 * 1024 * 1024),
    ("grpc.max_receive_message_length", 4 * 1024 * 1024),
    ("grpc.keepalive_time_ms", 30_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.http2.max_pings_without_data", 0),
    ("grpc.enable_retries", 0),
)


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
_log_exporter = OTLPLogExporter(insecure=True, channel_options=_GRPC_CHANNEL_OPTIONS)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(
    _log_exporter,
    # Cap the in-process queue.  Default is 2048 records; at ~8 log records/s
    # (2 users × 4 log.info calls per task) this fills in 256 s and then drops
    # records rather than growing the C heap unboundedly.
    max_queue_size=512,
    max_export_batch_size=128,
))
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
_metric_exporter = OTLPMetricExporter(insecure=True, channel_options=_GRPC_CHANNEL_OPTIONS)
# Drop all attributes from every metric emitted by SystemMetricsInstrumentor.
# Without this the OTel SDK retains one _AttributesAggregation entry per unique
# attribute-set (per-CPU, per-disk-device, per-network-interface, per-state…)
# for the entire lifetime of the MeterProvider — confirmed ~50 MB/h RSS growth.
#
# The wildcard matches every instrument registered against this MeterProvider.
# We do not need per-CPU/device breakdown in any dashboard, so collapsing to a
# single unlabelled bucket per metric name is acceptable.
#
# NOTE: the previous fix used an explicit name list which was incomplete —
# it missed process.* instruments and used wrong names (e.g. "dropped.packets"
# instead of the actual "dropped_packets").  A wildcard is both simpler and
# future-proof against instrumentation library updates.
_drop_all_attrs = View(instrument_name="*", attribute_keys=set())
set_meter_provider(MeterProvider(
    [PeriodicExportingMetricReader(_metric_exporter)],
    views=[_drop_all_attrs],
))

# ---------------------------------------------------------------------------
# Traces — not used
# ---------------------------------------------------------------------------
# This process generates zero spans: there are no explicit tracer.start_span()
# calls in users.py or page_actions.py, and the Playwright browser network
# stack bypasses Python's requests/urllib3 (so those instrumentors produce
# nothing either).  A TracerProvider + BatchSpanProcessor + OTLPSpanExporter
# would open a third idle gRPC channel and run a background export goroutine
# for nothing.  Omitted entirely.

# ---------------------------------------------------------------------------
# Instrumentors
# Only SystemMetricsInstrumentor is registered — this process does no Python-
# level HTTP (Playwright uses Chromium's network stack), has no Jinja2 templates,
# and generates zero traces.  Jinja2/Requests/URLLib3 instrumentors were
# previously loaded but produced no spans and added unnecessary monkey-patching.
# ---------------------------------------------------------------------------
SystemMetricsInstrumentor().instrument()
logging.info("Instrumentation complete")
