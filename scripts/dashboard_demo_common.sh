#!/bin/bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="${NAMESPACE:-default}"
TRANSACTION_GRAPH_SERVICE="${TRANSACTION_GRAPH_SERVICE:-svc/transaction-graph}"
FRAUD_DASHBOARD_SERVICE="${FRAUD_DASHBOARD_SERVICE:-svc/fraud-dashboard}"
KAFKA_TARGET="${KAFKA_TARGET:-deploy/kafka}"
ALERTING_TARGET="${ALERTING_TARGET:-deploy/alerting}"
ALERTING_DEPLOYMENT="${ALERTING_DEPLOYMENT:-deployment/alerting}"
NEO4J_TARGET="${NEO4J_TARGET:-deploy/neo4j}"
KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
KAFKA_FRAUD_ALERTS_TOPIC="${KAFKA_FRAUD_ALERTS_TOPIC:-fraud.alerts}"
GRAPH_PORT="${GRAPH_PORT:-49004}"
DASHBOARD_PORT="${DASHBOARD_PORT:-43000}"
GRAPH_LIMIT="${GRAPH_LIMIT:-40}"
VERIFY_DASHBOARD="${VERIFY_DASHBOARD:-true}"
EXPECTED_ACCOUNTS_COUNT="${EXPECTED_ACCOUNTS_COUNT:-}"
EXPECTED_ALERT_COUNT="${EXPECTED_ALERT_COUNT:-}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
VERIFY_TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-60}"

PORT_FORWARD_PIDS=()

dashboard_demo_require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

dashboard_demo_cleanup() {
  local pid
  for pid in "${PORT_FORWARD_PIDS[@]:-}"; do
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
      for _ in 1 2 3 4; do
        if ! kill -0 "${pid}" >/dev/null 2>&1; then
          break
        fi
        sleep 0.5
      done
      if kill -0 "${pid}" >/dev/null 2>&1; then
        kill -9 "${pid}" >/dev/null 2>&1 || true
      fi
      wait "${pid}" 2>/dev/null || true
    fi
  done
}

dashboard_demo_wait_for_http() {
  local url="$1"
  local timeout_seconds="$2"
  python3 - "$url" "$timeout_seconds" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
timeout_seconds = int(sys.argv[2])
deadline = time.time() + timeout_seconds
last_error = None

while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if 200 <= response.status < 500:
                sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        time.sleep(1)

raise SystemExit(f"Timed out waiting for {url}: {last_error}")
PY
}

dashboard_demo_start_port_forward() {
  local resource="$1"
  local port_mapping="$2"
  local health_url="$3"

  kubectl port-forward -n "${NAMESPACE}" "${resource}" "${port_mapping}" >/dev/null 2>&1 &
  local pf_pid=$!
  disown "${pf_pid}" 2>/dev/null || true
  PORT_FORWARD_PIDS+=("${pf_pid}")
  dashboard_demo_wait_for_http "${health_url}" 30
}

dashboard_demo_start_transaction_graph_port_forward() {
  echo "Starting transaction-graph port-forward on localhost:${GRAPH_PORT}..."
  dashboard_demo_start_port_forward "${TRANSACTION_GRAPH_SERVICE}" "${GRAPH_PORT}:9004" "http://127.0.0.1:${GRAPH_PORT}/health"
}

dashboard_demo_start_dashboard_port_forward() {
  echo "Starting fraud-dashboard port-forward on localhost:${DASHBOARD_PORT}..."
  dashboard_demo_start_port_forward "${FRAUD_DASHBOARD_SERVICE}" "${DASHBOARD_PORT}:3001" "http://127.0.0.1:${DASHBOARD_PORT}/"
}

dashboard_demo_ensure_topic() {
  kubectl exec -n "${NAMESPACE}" "${KAFKA_TARGET}" -- \
    kafka-topics --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" \
    --create --if-not-exists --topic "${KAFKA_FRAUD_ALERTS_TOPIC}" \
    --partitions 1 --replication-factor 1 >/dev/null
}

dashboard_demo_clear_graph() {
  kubectl exec -n "${NAMESPACE}" "${NEO4J_TARGET}" -- \
    cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" "MATCH (n) DETACH DELETE n" >/dev/null
}

dashboard_demo_restart_alerting() {
  kubectl rollout restart "${ALERTING_DEPLOYMENT}" -n "${NAMESPACE}" >/dev/null
  kubectl rollout status "${ALERTING_DEPLOYMENT}" -n "${NAMESPACE}" --timeout=180s >/dev/null
}

dashboard_demo_seed_graph() {
  python3 "${ROOT_DIR}/scripts/load_transaction_graph_processed.py" \
    --api-base-url "http://127.0.0.1:${GRAPH_PORT}" \
    --limit "${GRAPH_LIMIT}"
}

dashboard_demo_publish_alerts() {
  kubectl exec -i -n "${NAMESPACE}" "${ALERTING_TARGET}" -- \
    env KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS}" \
    KAFKA_FRAUD_ALERTS_TOPIC="${KAFKA_FRAUD_ALERTS_TOPIC}" \
    python - <<'PY'
from confluent_kafka import Producer
import json
import os

topic = os.environ["KAFKA_FRAUD_ALERTS_TOPIC"]
producer = Producer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
alerts = [
    {
        "alert_id": "dash-alert-001",
        "tx_id": "elliptic-edge-1-230425980-5530458",
        "severity": "high",
        "confidence_score": 0.98,
        "reason": "Rapid fan-out transfer pattern",
        "status": "open",
    },
    {
        "alert_id": "dash-alert-002",
        "tx_id": "elliptic-edge-5-232013274-232029206",
        "severity": "medium",
        "confidence_score": 0.87,
        "reason": "Unusual counterparty behavior",
        "status": "open",
    },
    {
        "alert_id": "dash-alert-003",
        "tx_id": "elliptic-edge-12-88008478-232012569",
        "severity": "critical",
        "confidence_score": 0.995,
        "reason": "Known illicit cluster proximity",
        "status": "escalated",
    },
    {
        "alert_id": "dash-alert-004",
        "tx_id": "elliptic-edge-21-69254632-230595355",
        "severity": "low",
        "confidence_score": 0.72,
        "reason": "Velocity anomaly follow-up",
        "status": "open",
    },
    {
        "alert_id": "dash-alert-005",
        "tx_id": "elliptic-edge-33-3878856-3878886",
        "severity": "high",
        "confidence_score": 0.93,
        "reason": "Cross-hop layering signature",
        "status": "investigating",
    },
]

for alert in alerts:
    producer.produce(topic, json.dumps(alert).encode("utf-8"))
producer.flush(10)
print(json.dumps({"published_alerts": len(alerts), "topic": topic}, indent=2))
PY
}

dashboard_demo_verify_dashboard() {
  local expected_accounts="$1"
  local expected_alerts="$2"
  python3 - "http://127.0.0.1:${DASHBOARD_PORT}/api/transaction-graph/accounts?limit=10" \
    "http://127.0.0.1:${DASHBOARD_PORT}/api/alerting/alerts/recent?limit=10" \
    "${expected_accounts}" "${expected_alerts}" "${VERIFY_TIMEOUT_SECONDS}" <<'PY'
import json
import sys
import time
import urllib.request

accounts_url = sys.argv[1]
alerts_url = sys.argv[2]
expected_accounts = sys.argv[3]
expected_alerts = sys.argv[4]
verify_timeout_seconds = int(sys.argv[5])

deadline = time.time() + verify_timeout_seconds
last_error = None

while time.time() < deadline:
    try:
        with urllib.request.urlopen(accounts_url, timeout=10) as response:
            accounts = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(alerts_url, timeout=10) as response:
            alerts = json.loads(response.read().decode("utf-8"))

        accounts_count = accounts.get("count", len(accounts.get("accounts", [])))
        alerts_count = len(alerts)

        accounts_ok = (not expected_accounts) or accounts_count == int(expected_accounts)
        alerts_ok = (not expected_alerts) or alerts_count == int(expected_alerts)
        if accounts_ok and alerts_ok:
            print(
                json.dumps(
                    {
                        "dashboard_accounts_count": accounts_count,
                        "dashboard_alert_count": alerts_count,
                        "sample_account": (accounts.get("accounts") or [None])[0],
                        "sample_alert": alerts[0] if alerts else None,
                    },
                    indent=2,
                )
            )
            sys.exit(0)

        last_error = (
            f"Expected accounts={expected_accounts or '*'} alerts={expected_alerts or '*'}, "
            f"found accounts={accounts_count} alerts={alerts_count}"
        )
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
    time.sleep(1)

raise SystemExit(f"Dashboard verification timed out: {last_error}")
PY
}
