#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# OTel setup must be imported first — it registers providers and instrumentors
# as a side effect before Locust discovers user classes.
import otel_setup  # noqa: F401

from users import WebsiteBrowserUser  # noqa: F401 — Locust discovers this class
