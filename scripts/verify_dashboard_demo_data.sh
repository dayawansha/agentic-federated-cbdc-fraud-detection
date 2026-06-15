#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dashboard_demo_common.sh"

trap dashboard_demo_cleanup EXIT

dashboard_demo_require_cmd kubectl
dashboard_demo_require_cmd python3

dashboard_demo_start_dashboard_port_forward

echo "Verifying dashboard proxy responses..."
dashboard_demo_verify_dashboard "${EXPECTED_ACCOUNTS_COUNT}" "${EXPECTED_ALERT_COUNT}"

echo
echo "Dashboard demo data verification complete."
