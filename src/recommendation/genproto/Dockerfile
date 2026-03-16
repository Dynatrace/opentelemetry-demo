# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim-bookworm

WORKDIR /build

RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir setuptools==69.5.1 wheel grpcio-tools==1.59.2
