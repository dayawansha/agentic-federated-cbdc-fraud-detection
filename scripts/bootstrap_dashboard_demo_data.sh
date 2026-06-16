#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dashboard_demo_common.sh"

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
  dashboard_demo_verify_dashboard "${EXPECTED_ACCOUNTS_COUNT}" "${EXPECTED_ALERT_COUNT}"
fi

echo
echo "Dashboard demo data bootstrap complete."
