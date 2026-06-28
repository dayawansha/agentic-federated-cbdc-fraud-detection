#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-full}"

source "${SCRIPT_DIR}/dashboard_demo_common.sh"

run_reset() {
  trap dashboard_demo_cleanup EXIT
  dashboard_demo_require_cmd kubectl
  dashboard_demo_require_cmd python3

  if [[ "${VERIFY_DASHBOARD}" == "true" ]]; then
    dashboard_demo_start_dashboard_port_forward
  fi

  echo "Clearing Neo4j transaction graph..."
  dashboard_demo_clear_graph

  echo "Restarting alerting to clear in-memory recent alerts..."
  dashboard_demo_restart_alerting

  if [[ "${VERIFY_DASHBOARD}" == "true" ]]; then
    echo "Verifying dashboard is empty after reset..."
    dashboard_demo_verify_dashboard "0" "0"
  fi

  echo
  echo "Dashboard demo data reset complete."
}

run_seed() {
  trap dashboard_demo_cleanup EXIT
  dashboard_demo_require_cmd kubectl
  dashboard_demo_require_cmd python3

  dashboard_demo_start_transaction_graph_port_forward

  if [[ "${VERIFY_DASHBOARD}" == "true" ]]; then
    dashboard_demo_start_dashboard_port_forward
  fi

  echo "Ensuring Kafka topic ${KAFKA_FRAUD_ALERTS_TOPIC} exists..."
  dashboard_demo_ensure_topic

  echo "Loading ${GRAPH_LIMIT} processed transactions from ${GRAPH_NODES_PATH} into transaction-graph..."
  dashboard_demo_seed_graph

  echo "Publishing demo fraud alerts into ${KAFKA_FRAUD_ALERTS_TOPIC}..."
  dashboard_demo_publish_alerts

  if [[ "${VERIFY_DASHBOARD}" == "true" ]]; then
    echo "Verifying dashboard proxy responses..."
    dashboard_demo_verify_dashboard "${EXPECTED_ACCOUNTS_COUNT:-10}" "${EXPECTED_ALERT_COUNT:-5}"
  fi

  echo
  echo "Dashboard demo data bootstrap complete."
}

run_verify() {
  trap dashboard_demo_cleanup EXIT
  dashboard_demo_require_cmd kubectl
  dashboard_demo_require_cmd python3

  dashboard_demo_start_dashboard_port_forward

  echo "Verifying dashboard proxy responses..."
  dashboard_demo_verify_dashboard "${EXPECTED_ACCOUNTS_COUNT:-10}" "${EXPECTED_ALERT_COUNT:-5}"

  echo
  echo "Dashboard demo data verification complete."
}

run_full() {
  trap dashboard_demo_cleanup EXIT
  dashboard_demo_require_cmd kubectl
  dashboard_demo_require_cmd python3

  dashboard_demo_start_dashboard_port_forward

  echo "Clearing Neo4j transaction graph..."
  dashboard_demo_clear_graph

  echo "Restarting alerting to clear in-memory recent alerts..."
  dashboard_demo_restart_alerting

  echo "Verifying dashboard is empty after reset..."
  dashboard_demo_verify_dashboard "0" "0"

  dashboard_demo_start_transaction_graph_port_forward

  echo "Ensuring Kafka topic ${KAFKA_FRAUD_ALERTS_TOPIC} exists..."
  dashboard_demo_ensure_topic

  echo "Loading ${GRAPH_LIMIT} processed transactions into transaction-graph..."
  dashboard_demo_seed_graph

  echo "Publishing demo fraud alerts into ${KAFKA_FRAUD_ALERTS_TOPIC}..."
  dashboard_demo_publish_alerts

  echo "Verifying dashboard proxy responses..."
  dashboard_demo_verify_dashboard "${EXPECTED_ACCOUNTS_COUNT:-10}" "${EXPECTED_ALERT_COUNT:-5}"

  echo
  echo "Dashboard demo lifecycle complete."
}

usage() {
  cat <<'EOF'
Usage: bash scripts/demo_dashboard_lifecycle.sh [full|reset|seed|verify]

Modes:
  full    Reset demo state, seed demo data, then verify dashboard counts
  reset   Clear graph data and alert cache, then verify the dashboard is empty
  seed    Seed graph data and alerts, then verify the dashboard is populated
  verify  Verify dashboard proxy counts without changing data

Environment:
  GRAPH_LIMIT=300
  DASHBOARD_PORT=43000
  GRAPH_PORT=49004
  EXPECTED_ACCOUNTS_COUNT
  EXPECTED_ALERT_COUNT
  VERIFY_DASHBOARD=true
EOF
}

case "${MODE}" in
  full)
    run_full
    ;;
  reset)
    run_reset
    ;;
  seed)
    run_seed
    ;;
  verify)
    run_verify
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "Unknown mode: ${MODE}" >&2
    usage >&2
    exit 1
    ;;
esac
