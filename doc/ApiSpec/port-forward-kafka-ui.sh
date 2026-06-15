#!/usr/bin/env bash

set -euo pipefail

LOCAL_PORT="${KAFKA_UI_LOCAL_PORT:-18080}"
OPEN_BROWSER=0

if [[ "${1:-}" == "--open" ]]; then
  OPEN_BROWSER=1
fi

is_port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

find_available_port() {
  local port="$1"
  local attempts=20

  for ((i = 0; i < attempts; i++)); do
    if ! is_port_in_use "${port}"; then
      echo "${port}"
      return 0
    fi
    port=$((port + 1))
  done

  return 1
}

cleanup() {
  if [[ -n "${PF_PID:-}" ]] && kill -0 "${PF_PID}" 2>/dev/null; then
    kill "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

SELECTED_PORT="$(find_available_port "${LOCAL_PORT}")" || {
  echo "Could not find a free local port starting from ${LOCAL_PORT}."
  echo "Set KAFKA_UI_LOCAL_PORT to an unused port and try again."
  exit 1
}

if [[ "${SELECTED_PORT}" != "${LOCAL_PORT}" ]]; then
  echo "Local port ${LOCAL_PORT} is already in use. Falling back to ${SELECTED_PORT}."
fi

echo "Starting Kafka UI port-forward..."
kubectl port-forward svc/kafka-ui "${SELECTED_PORT}:8080" >/tmp/kafka-ui-port-forward.log 2>&1 &
PF_PID=$!

sleep 2

if ! kill -0 "${PF_PID}" 2>/dev/null; then
  echo "Kafka UI port-forward failed. Check /tmp/kafka-ui-port-forward.log"
  exit 1
fi

echo
echo "Kafka UI is available at:"
echo "  http://127.0.0.1:${SELECTED_PORT}"
echo
echo "Expected system Kafka view:"
echo "  Cluster : federated-fraud-kafka"
echo "  Broker  : kafka:9092 (id: 1)"
echo "  Topics  : transactions.events, fraud.alerts"
echo "  Internal: __consumer_offsets"
echo
echo "Press Ctrl+C to stop the port-forward."

if [[ "${OPEN_BROWSER}" -eq 1 ]]; then
  open "http://127.0.0.1:${SELECTED_PORT}"
fi

wait "${PF_PID}"
