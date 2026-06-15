#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dashboard_demo_common.sh"

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
