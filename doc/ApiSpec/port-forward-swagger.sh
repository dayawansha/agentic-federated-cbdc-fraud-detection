#!/usr/bin/env bash

set -euo pipefail

OPEN_BROWSER=0
if [[ "${1:-}" == "--open" ]]; then
  OPEN_BROWSER=1
fi

SERVICES=(
  "agentic-coordinator:8001"
  "secure-aggregator:8002"
  "policy-manager:8003"
  "model-registry:8004"
  "local-agent:9001"
  "local-gnn:9002"
  "privacy-layer:9003"
  "transaction-graph:9004"
  "alerting:9005"
)

PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}

trap cleanup EXIT INT TERM

for entry in "${SERVICES[@]}"; do
  service_name="${entry%%:*}"
  port="${entry##*:}"

  echo "Forwarding ${service_name} on http://127.0.0.1:${port}"
  kubectl port-forward "svc/${service_name}" "${port}:${port}" >/tmp/"${service_name}"-swagger.log 2>&1 &
  PIDS+=("$!")
done

sleep 3

echo
echo "Swagger URLs:"
for entry in "${SERVICES[@]}"; do
  service_name="${entry%%:*}"
  port="${entry##*:}"
  echo "- ${service_name}: http://127.0.0.1:${port}/docs"
  echo "  OpenAPI JSON: http://127.0.0.1:${port}/openapi.json"
done

echo
echo "Open doc/ApiSpec/index.html for the full index."
echo "Press Ctrl+C to stop all port-forwards."

if [[ "${OPEN_BROWSER}" -eq 1 ]]; then
  open "/Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/doc/ApiSpec/index.html"
fi

wait
