#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/deploy_common.sh"

IMAGE_TAG="${IMAGE_TAG:-ci-smoke}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-minikube}"
NAMESPACE="${NAMESPACE:-default}"
RELEASE_NAME="${RELEASE_NAME:-federated-fraud}"
MINIKUBE_DRIVER="${MINIKUBE_DRIVER:-docker}"
MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-8192}"
MINIKUBE_DISK_SIZE="${MINIKUBE_DISK_SIZE:-40g}"
GRAPH_LIMIT="${GRAPH_LIMIT:-300}"
EXPECTED_ACCOUNTS_COUNT="${EXPECTED_ACCOUNTS_COUNT:-10}"
EXPECTED_ALERT_COUNT="${EXPECTED_ALERT_COUNT:-5}"
START_MINIKUBE_IF_NEEDED=true
SKIP_BUILD=false
SKIP_DEPLOY=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Runs a deployment smoke check that proves the dashboard lifecycle:
reset -> seed -> verify

Options:
  --tag <tag>                Docker image tag to build and deploy
  --profile <name>           Minikube profile name (default: ${MINIKUBE_PROFILE})
  --namespace <ns>           Kubernetes namespace (default: ${NAMESPACE})
  --release <name>           Helm release name (default: ${RELEASE_NAME})
  --skip-build               Reuse existing local images for IMAGE_TAG
  --skip-deploy              Reuse the currently deployed cluster state
  --skip-minikube-start      Fail instead of starting minikube when it is not running
  --help                     Show this help message

Environment:
  IMAGE_TAG                  Same as --tag
  MINIKUBE_PROFILE           Same as --profile
  EXPECTED_CONTEXT           kubectl context guard (default: minikube)
  MINIKUBE_DRIVER            Default: docker
  MINIKUBE_CPUS              Default: 4
  MINIKUBE_MEMORY            Default: 8192
  MINIKUBE_DISK_SIZE         Default: 40g
  GRAPH_LIMIT                Default: 300
  EXPECTED_ACCOUNTS_COUNT    Default: 10
  EXPECTED_ALERT_COUNT       Default: 5
EOF
}

dump_failure_context() {
  echo
  echo "Smoke test failed. Collecting cluster context..." >&2
  kubectl get pods -n "${NAMESPACE}" -o wide || true
  kubectl get events -n "${NAMESPACE}" --sort-by=.lastTimestamp | tail -n 200 || true
  for deployment in "${APP_DEPLOYMENTS[@]}"; do
    echo
    echo "===== logs: deployment/${deployment} =====" >&2
    kubectl logs "deployment/${deployment}" -n "${NAMESPACE}" --tail=80 || true
  done
}

on_exit() {
  local exit_code=$?
  if [[ "${exit_code}" -ne 0 ]]; then
    dump_failure_context
  fi
  exit "${exit_code}"
}

ensure_minikube_running() {
  if minikube -p "${MINIKUBE_PROFILE}" status >/dev/null 2>&1; then
    return 0
  fi

  if [[ "${START_MINIKUBE_IF_NEEDED}" != "true" ]]; then
    echo "Minikube profile '${MINIKUBE_PROFILE}' is not running." >&2
    exit 1
  fi

  echo "Starting minikube profile ${MINIKUBE_PROFILE}..."
  minikube start \
    -p "${MINIKUBE_PROFILE}" \
    --driver="${MINIKUBE_DRIVER}" \
    --container-runtime=containerd \
    --cpus="${MINIKUBE_CPUS}" \
    --memory="${MINIKUBE_MEMORY}" \
    --disk-size="${MINIKUBE_DISK_SIZE}"
}

ensure_context() {
  local current_context
  current_context="$(kubectl config current-context 2>/dev/null || true)"
  if [[ "${current_context}" != "${EXPECTED_CONTEXT}" ]]; then
    kubectl config use-context "${EXPECTED_CONTEXT}"
  fi
  ensure_expected_context "${EXPECTED_CONTEXT}" \
    "Set EXPECTED_CONTEXT to override this smoke-test guard if you intentionally want another local cluster."
}

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
    --skip-deploy)
      SKIP_DEPLOY=true
      shift
      ;;
    --skip-minikube-start)
      START_MINIKUBE_IF_NEEDED=false
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

trap on_exit EXIT

mapfile -t APP_DEPLOYMENTS < <(project_app_deployments)

require_cmd docker
require_cmd kubectl
require_cmd helm
require_cmd minikube
require_cmd python3

cd "${ROOT_DIR}"

ensure_minikube_running
ensure_context

if [[ "${SKIP_BUILD}" != "true" ]]; then
  echo "Building images with tag ${IMAGE_TAG}..."
  IMAGE_TAG="${IMAGE_TAG}" bash scripts/build_all_images.sh --tag "${IMAGE_TAG}"
fi

if [[ "${SKIP_DEPLOY}" != "true" ]]; then
  echo "Deploying Helm release ${RELEASE_NAME} with image tag ${IMAGE_TAG}..."
  IMAGE_TAG="${IMAGE_TAG}" \
    MINIKUBE_PROFILE="${MINIKUBE_PROFILE}" \
    EXPECTED_CONTEXT="${EXPECTED_CONTEXT}" \
    NAMESPACE="${NAMESPACE}" \
    RELEASE_NAME="${RELEASE_NAME}" \
    bash scripts/deploy_minikube.sh \
      --tag "${IMAGE_TAG}" \
      --profile "${MINIKUBE_PROFILE}" \
      --namespace "${NAMESPACE}" \
      --release "${RELEASE_NAME}"
fi

echo "Running dashboard lifecycle smoke test..."
GRAPH_LIMIT="${GRAPH_LIMIT}" \
  EXPECTED_ACCOUNTS_COUNT="${EXPECTED_ACCOUNTS_COUNT}" \
  EXPECTED_ALERT_COUNT="${EXPECTED_ALERT_COUNT}" \
  NAMESPACE="${NAMESPACE}" \
  bash scripts/demo_dashboard_lifecycle.sh full

echo
echo "CI dashboard smoke test passed."
