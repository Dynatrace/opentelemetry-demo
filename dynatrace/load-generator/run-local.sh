#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-${SCRIPT_DIR}/.venv}"

if [[ ! -x "${VENV_DIR}/bin/locust" ]]; then
  echo "Locust was not found at ${VENV_DIR}/bin/locust."
  echo "Install dependencies first:"
  echo "  python3 -m venv ${VENV_DIR}"
  echo "  ${VENV_DIR}/bin/pip install -r ${SCRIPT_DIR}/requirements.txt"
  echo "  ${VENV_DIR}/bin/playwright install --with-deps chromium"
  exit 1
fi

export LOCUST_HOST="${LOCUST_HOST:-http://localhost:8080}"
export LOCUST_USERS="${LOCUST_USERS:-1}"
export LOCUST_SPAWN_RATE="${LOCUST_SPAWN_RATE:-1}"
export LOCUST_WEB_PORT="${LOCUST_WEB_PORT:-8089}"
export LOCUST_AUTOSTART="${LOCUST_AUTOSTART:-true}"
export LOCUST_HEADLESS="${LOCUST_HEADLESS:-false}"
export BROWSER_HEADLESS="${BROWSER_HEADLESS:-false}"
export SYNTHETIC_REQUEST_ENABLED="${SYNTHETIC_REQUEST_ENABLED:-false}"
export OTEL_SDK_DISABLED="${OTEL_SDK_DISABLED:-true}"

echo "Starting Dynatrace load generator"
echo "  target: ${LOCUST_HOST}"
echo "  users: ${LOCUST_USERS}"
echo "  web UI: http://localhost:${LOCUST_WEB_PORT}"
echo "  browser headless: ${BROWSER_HEADLESS}"

exec "${VENV_DIR}/bin/locust" \
  --skip-log-setup \
  --locustfile "${SCRIPT_DIR}/src/locustfile.py" \
  --host "${LOCUST_HOST}" \
  --users "${LOCUST_USERS}" \
  --spawn-rate "${LOCUST_SPAWN_RATE}" \
  --web-port "${LOCUST_WEB_PORT}" \
  "$@"
