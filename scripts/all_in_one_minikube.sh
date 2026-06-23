#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="${ROOT_DIR}/scripts"
STATE_DIR="${ROOT_DIR}/.local-state/all-in-one"
PID_FILE="${STATE_DIR}/port-forwards.pid"
META_FILE="${STATE_DIR}/runtime.env"
LOG_DIR="${STATE_DIR}/logs"

COMMAND="${1:-up}"
if [[ $# -gt 0 ]]; then
  shift
fi

MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-minikube}"
NAMESPACE="${NAMESPACE:-default}"
RELEASE_NAME="${RELEASE_NAME:-federated-fraud}"
IMAGE_TAG="${IMAGE_TAG:-}"
SKIP_BUILD=false
SKIP_SEED=false
SKIP_HEALTH_CHECKS=false
SKIP_E2E=false
START_MINIKUBE=false

MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-8192}"
MINIKUBE_DISK_SIZE="${MINIKUBE_DISK_SIZE:-40g}"

PORT_FORWARDS=(
  "agentic-coordinator|service/agentic-coordinator|8001:8001"
  "federated-model-aggregator|service/federated-model-aggregator|8002:8002"
  "policy-manager|service/policy-manager|8003:8003"
  "model-registry|service/model-registry|8004:8004"
  "local-agent|service/local-agent|9001:9001"
  "local-gnn|service/local-gnn|9002:9002"
  "privacy-layer|service/privacy-layer|9003:9003"
  "transaction-graph|service/transaction-graph|9004:9004"
  "alerting|service/alerting|9005:9005"
  "fraud-dashboard|service/fraud-dashboard|3001:3001"
  "kafka-ui|service/kafka-ui|8080:8080"
)

usage() {
  cat <<EOF
Usage: $(basename "$0") <up|down|status> [options]

Commands:
  up                 Start minikube if needed, build images, deploy all services, and start all port-forwards
  down               Stop all port-forwards started by this script
  status             Show deployment and port-forward status

Options for 'up':
  --tag <tag>        Explicit image tag to use
  --profile <name>   Minikube profile (default: ${MINIKUBE_PROFILE})
  --namespace <ns>   Kubernetes namespace (default: ${NAMESPACE})
  --release <name>   Helm release name (default: ${RELEASE_NAME})
  --skip-build       Reuse existing images for the chosen tag
  --skip-seed        Skip dashboard demo data bootstrap
  --skip-health-checks Skip post-deploy health checks
  --skip-e2e         Skip post-deploy federated E2E test
  --start-minikube   Start minikube automatically if not already running
  --help             Show this help message

Environment:
  IMAGE_TAG          Same as --tag
  MINIKUBE_PROFILE   Same as --profile
  EXPECTED_CONTEXT   kubectl context guard (default: minikube)
  MINIKUBE_CPUS      minikube start CPUs (default: ${MINIKUBE_CPUS})
  MINIKUBE_MEMORY    minikube start memory in MB (default: ${MINIKUBE_MEMORY})
  MINIKUBE_DISK_SIZE minikube disk size (default: ${MINIKUBE_DISK_SIZE})

Examples:
  bash scripts/all_in_one_minikube.sh up --start-minikube
  bash scripts/all_in_one_minikube.sh up --tag local-manual-001 --skip-seed
  bash scripts/all_in_one_minikube.sh status
  bash scripts/all_in_one_minikube.sh down
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_state_dirs() {
  mkdir -p "${STATE_DIR}" "${LOG_DIR}"
}

parse_up_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --tag)
        IMAGE_TAG="$2"
        shift 2
        ;;
      --profile)
        MINIKUBE_PROFILE="$2"
        shift 2
        ;;
      --namespace)
        NAMESPACE="$2"
        shift 2
        ;;
      --release)
        RELEASE_NAME="$2"
        shift 2
        ;;
      --skip-build)
        SKIP_BUILD=true
        shift
        ;;
      --skip-seed)
        SKIP_SEED=true
        shift
        ;;
      --skip-health-checks)
        SKIP_HEALTH_CHECKS=true
        shift
        ;;
      --skip-e2e)
        SKIP_E2E=true
        shift
        ;;
      --start-minikube)
        START_MINIKUBE=true
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

check_context() {
  local current_context
  current_context="$(kubectl config current-context)"
  if [[ "${current_context}" != "${EXPECTED_CONTEXT}" ]]; then
    echo "Current kubectl context is '${current_context}', expected '${EXPECTED_CONTEXT}'." >&2
    echo "Run: kubectl config use-context ${EXPECTED_CONTEXT}" >&2
    exit 1
  fi
}

ensure_minikube_running() {
  if minikube -p "${MINIKUBE_PROFILE}" status >/dev/null 2>&1; then
    return 0
  fi

  if [[ "${START_MINIKUBE}" != "true" ]]; then
    echo "Minikube profile '${MINIKUBE_PROFILE}' is not running." >&2
    echo "Use --start-minikube or start it manually first." >&2
    exit 1
  fi

  echo "Starting minikube profile ${MINIKUBE_PROFILE}..."
  minikube start \
    -p "${MINIKUBE_PROFILE}" \
    --driver=docker \
    --container-runtime=containerd \
    --cpus="${MINIKUBE_CPUS}" \
    --memory="${MINIKUBE_MEMORY}" \
    --disk-size="${MINIKUBE_DISK_SIZE}"
}

resolve_tag() {
  if [[ -n "${IMAGE_TAG}" ]]; then
    return 0
  fi
  IMAGE_TAG="$(
    MINIKUBE_PROFILE="${MINIKUBE_PROFILE}" \
    EXPECTED_CONTEXT="${EXPECTED_CONTEXT}" \
    NAMESPACE="${NAMESPACE}" \
    RELEASE_NAME="${RELEASE_NAME}" \
    bash "${SCRIPT_DIR}/local_minikube_release.sh" --print-tag
  )"
}

deploy_stack() {
  local deploy_args=(
    --tag "${IMAGE_TAG}"
    --profile "${MINIKUBE_PROFILE}"
    --namespace "${NAMESPACE}"
    --release "${RELEASE_NAME}"
  )

  if [[ "${SKIP_BUILD}" == "true" ]]; then
    deploy_args+=(--skip-build)
  fi

  EXPECTED_CONTEXT="${EXPECTED_CONTEXT}" \
    bash "${SCRIPT_DIR}/local_minikube_release.sh" "${deploy_args[@]}"
}

wait_for_service() {
  local resource="$1"
  local pod=""
  local tries=30

  while [[ ${tries} -gt 0 ]]; do
    if pod="$(kubectl get "${resource}" -n "${NAMESPACE}" -o name 2>/dev/null | head -n 1)" && [[ -n "${pod}" ]]; then
      return 0
    fi
    tries=$((tries - 1))
    sleep 2
  done

  echo "Timed out waiting for ${resource} in namespace ${NAMESPACE}" >&2
  return 1
}

cleanup_existing_port_forwards() {
  if [[ ! -f "${PID_FILE}" ]]; then
    return 0
  fi

  while IFS='|' read -r name pid _rest; do
    [[ -z "${pid}" ]] && continue
    if kill -0 "${pid}" >/dev/null 2>&1; then
      echo "Stopping existing port-forward ${name} (pid ${pid})..."
      kill "${pid}" >/dev/null 2>&1 || true
      wait "${pid}" 2>/dev/null || true
    fi
  done < "${PID_FILE}"

  rm -f "${PID_FILE}"
}

start_port_forwards() {
  ensure_state_dirs
  cleanup_existing_port_forwards
  : > "${PID_FILE}"

  local entry name resource port_spec log_file pid
  for entry in "${PORT_FORWARDS[@]}"; do
    name="${entry%%|*}"
    resource="${entry#*|}"
    resource="${resource%%|*}"
    port_spec="${entry##*|}"
    log_file="${LOG_DIR}/${name}.log"

    wait_for_service "${resource}" "${port_spec}"

    echo "Starting port-forward ${name} (${port_spec})..."
    kubectl port-forward -n "${NAMESPACE}" "${resource}" "${port_spec}" >"${log_file}" 2>&1 &
    pid=$!
    sleep 2
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      echo "Port-forward ${name} failed. See ${log_file}" >&2
      exit 1
    fi
    echo "${name}|${pid}|${resource}|${port_spec}|${log_file}" >> "${PID_FILE}"
  done
}

record_runtime() {
  ensure_state_dirs
  cat > "${META_FILE}" <<EOF
IMAGE_TAG=${IMAGE_TAG}
MINIKUBE_PROFILE=${MINIKUBE_PROFILE}
EXPECTED_CONTEXT=${EXPECTED_CONTEXT}
NAMESPACE=${NAMESPACE}
RELEASE_NAME=${RELEASE_NAME}
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
}

seed_demo_data() {
  if [[ "${SKIP_SEED}" == "true" ]]; then
    echo "Skipping demo data bootstrap."
    return 0
  fi

  echo "Bootstrapping demo dashboard data..."
  bash "${SCRIPT_DIR}/bootstrap_dashboard_demo_data.sh"
}

run_health_checks() {
  if [[ "${SKIP_HEALTH_CHECKS}" == "true" ]]; then
    echo "Skipping post-deploy health checks."
    return 0
  fi

  require_cmd curl

  local checks=(
    "Agentic Coordinator|http://127.0.0.1:8001/health"
    "Federated Model Aggregator|http://127.0.0.1:8002/health"
    "Policy Manager|http://127.0.0.1:8003/health"
    "Model Registry|http://127.0.0.1:8004/health"
    "Local Agent|http://127.0.0.1:9001/health"
    "Local GNN|http://127.0.0.1:9002/health"
    "Privacy Layer|http://127.0.0.1:9003/health"
    "Transaction Graph|http://127.0.0.1:9004/health"
    "Alerting|http://127.0.0.1:9005/health"
  )

  local failures=0
  local check name url
  echo
  echo "Running post-deploy health checks..."
  for check in "${checks[@]}"; do
    name="${check%%|*}"
    url="${check##*|}"
    if curl --fail --silent --show-error "${url}" >/dev/null; then
      echo "  [PASS] ${name}"
    else
      echo "  [FAIL] ${name} -> ${url}" >&2
      failures=$((failures + 1))
    fi
  done

  return "${failures}"
}

run_e2e_test() {
  if [[ "${SKIP_E2E}" == "true" ]]; then
    echo "Skipping federated E2E test."
    return 0
  fi

  require_cmd python3
  echo
  echo "Running federated E2E test..."
  python3 "${SCRIPT_DIR}/e2e_fl_test.py"
}

show_status() {
  echo "Release status:"
  if [[ -f "${META_FILE}" ]]; then
    cat "${META_FILE}"
  else
    echo "No runtime metadata found."
  fi

  echo
  echo "Pods:"
  kubectl get pods -n "${NAMESPACE}" || true

  echo
  echo "Port-forwards:"
  if [[ -f "${PID_FILE}" ]]; then
    while IFS='|' read -r name pid resource port_spec log_file; do
      if kill -0 "${pid}" >/dev/null 2>&1; then
        echo "  ${name}: running (pid ${pid}) -> ${resource} ${port_spec}"
      else
        echo "  ${name}: stopped (pid ${pid}) -> see ${log_file}"
      fi
    done < "${PID_FILE}"
  else
    echo "  No active port-forwards managed by this script."
  fi
}

stop_port_forwards() {
  cleanup_existing_port_forwards
  echo "Stopped managed port-forwards."
}

print_summary() {
  local health_status="$1"
  local e2e_status="$2"

  echo
  echo "Final summary:"
  echo "  Deploy:         PASS"
  echo "  Port-forwards:  PASS"
  if [[ "${SKIP_HEALTH_CHECKS}" == "true" ]]; then
    echo "  Health checks:  SKIPPED"
  elif [[ "${health_status}" == "0" ]]; then
    echo "  Health checks:  PASS"
  else
    echo "  Health checks:  FAIL"
  fi

  if [[ "${SKIP_E2E}" == "true" ]]; then
    echo "  FL E2E test:    SKIPPED"
  elif [[ "${e2e_status}" == "0" ]]; then
    echo "  FL E2E test:    PASS"
  else
    echo "  FL E2E test:    FAIL"
  fi
}

print_endpoints() {
  cat <<EOF

All-in-one workflow complete.
Image tag: ${IMAGE_TAG}
Namespace: ${NAMESPACE}

Forwarded endpoints:
  Dashboard:            http://127.0.0.1:3001
  Agentic Coordinator:  http://127.0.0.1:8001
  Federated Model Aggregator: http://127.0.0.1:8002
  Policy Manager:       http://127.0.0.1:8003
  Model Registry:       http://127.0.0.1:8004
  Local Agent:          http://127.0.0.1:9001
  Local GNN:            http://127.0.0.1:9002
  Privacy Layer:        http://127.0.0.1:9003
  Transaction Graph:    http://127.0.0.1:9004
  Alerting:             http://127.0.0.1:9005
  Kafka UI:             http://127.0.0.1:8080

Useful follow-ups:
  bash scripts/demo_dashboard_lifecycle.sh verify
  bash scripts/all_in_one_minikube.sh status
  bash scripts/all_in_one_minikube.sh down
EOF
}

require_cmd bash
require_cmd kubectl
require_cmd minikube

case "${COMMAND}" in
  up)
    local_health_status=0
    local_e2e_status=0
    parse_up_args "$@"
    ensure_minikube_running
    kubectl config use-context "${EXPECTED_CONTEXT}" >/dev/null 2>&1 || true
    check_context
    resolve_tag
    deploy_stack
    start_port_forwards
    record_runtime
    seed_demo_data
    if run_health_checks; then
      local_health_status=0
    else
      local_health_status=$?
    fi
    if run_e2e_test; then
      local_e2e_status=0
    else
      local_e2e_status=$?
    fi
    show_status
    print_summary "${local_health_status}" "${local_e2e_status}"
    print_endpoints
    if [[ "${local_health_status}" != "0" || "${local_e2e_status}" != "0" ]]; then
      exit 1
    fi
    ;;
  down)
    stop_port_forwards
    ;;
  status)
    show_status
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    usage >&2
    exit 1
    ;;
esac
