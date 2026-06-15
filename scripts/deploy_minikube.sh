#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${ROOT_DIR}/infrastructure/helm/federated-fraud-detection"

RELEASE_NAME="${RELEASE_NAME:-federated-fraud}"
NAMESPACE="${NAMESPACE:-default}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-minikube}"
SKIP_LOAD=false
SKIP_HELM=false

IMAGES=(
  "dusman/federated-fraud-agentic-coordinator:${IMAGE_TAG}"
  "dusman/federated-fraud-secure-aggregator:${IMAGE_TAG}"
  "dusman/federated-fraud-policy-manager:${IMAGE_TAG}"
  "dusman/federated-fraud-model-registry:${IMAGE_TAG}"
  "dusman/federated-fraud-local-agent:${IMAGE_TAG}"
  "dusman/federated-fraud-local-gnn:${IMAGE_TAG}"
  "dusman/federated-fraud-privacy-layer:${IMAGE_TAG}"
  "dusman/federated-fraud-transaction-graph:${IMAGE_TAG}"
  "dusman/federated-fraud-alerting:${IMAGE_TAG}"
  "dusman/federated-fraud-fraud-dashboard:${IMAGE_TAG}"
)

APP_DEPLOYMENTS=(
  "agentic-coordinator"
  "secure-aggregator"
  "policy-manager"
  "model-registry"
  "local-agent"
  "local-gnn"
  "privacy-layer"
  "transaction-graph"
  "alerting"
  "fraud-dashboard"
)

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --tag <tag>          Docker image tag to load and deploy
  --profile <name>     Minikube profile name (default: ${MINIKUBE_PROFILE})
  --namespace <ns>     Helm release namespace (default: ${NAMESPACE})
  --release <name>     Helm release name (default: ${RELEASE_NAME})
  --skip-load          Skip minikube image loading
  --skip-helm          Skip Helm upgrade/install
  --help               Show this help message

Environment:
  IMAGE_TAG            Same as --tag
  MINIKUBE_PROFILE     Same as --profile
  EXPECTED_CONTEXT     kubectl context guard (default: minikube)
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

check_context() {
  local current_context
  current_context="$(kubectl config current-context)"
  if [[ "${current_context}" != "${EXPECTED_CONTEXT}" ]]; then
    echo "Current kubectl context is '${current_context}', expected '${EXPECTED_CONTEXT}'." >&2
    echo "Run 'kubectl config use-context ${EXPECTED_CONTEXT}' or override EXPECTED_CONTEXT intentionally." >&2
    exit 1
  fi
}

check_minikube() {
  if ! minikube -p "${MINIKUBE_PROFILE}" status >/dev/null 2>&1; then
    echo "Minikube profile '${MINIKUBE_PROFILE}' is not running." >&2
    echo "Start it first, for example: minikube start -p ${MINIKUBE_PROFILE}" >&2
    exit 1
  fi
}

check_images() {
  local missing=0
  local image

  for image in "${IMAGES[@]}"; do
    if ! docker image inspect "${image}" >/dev/null 2>&1; then
      echo "Missing local image: ${image}" >&2
      missing=1
    fi
  done

  if [[ "${missing}" -ne 0 ]]; then
    echo "Build the missing images first, for example with scripts/build_all_images.sh." >&2
    exit 1
  fi
}

load_images() {
  local image
  for image in "${IMAGES[@]}"; do
    echo "Loading ${image} into minikube profile ${MINIKUBE_PROFILE}..."
    minikube -p "${MINIKUBE_PROFILE}" image load "${image}"
  done
}

rollout_apps() {
  local deployment
  for deployment in "${APP_DEPLOYMENTS[@]}"; do
    echo "Waiting for deployment/${deployment}..."
    kubectl rollout status "deployment/${deployment}" -n "${NAMESPACE}" --timeout=180s
  done
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
    --skip-load)
      SKIP_LOAD=true
      shift
      ;;
    --skip-helm)
      SKIP_HELM=true
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

require_cmd docker
require_cmd kubectl
require_cmd helm
require_cmd minikube

MINIKUBE_DIR="${HOME}/.minikube"
MINIKUBE_PROFILE_DIR="${MINIKUBE_DIR}/profiles/${MINIKUBE_PROFILE}"

if [[ -d "${MINIKUBE_PROFILE_DIR}" ]]; then
  if ! (touch "${MINIKUBE_PROFILE_DIR}/.write_test" >/dev/null 2>&1 && rm -f "${MINIKUBE_PROFILE_DIR}/.write_test" >/dev/null 2>&1); then
    echo "Minikube profile directory is not writable: ${MINIKUBE_PROFILE_DIR}" >&2
    echo "Fix ownership/permissions, then retry:" >&2
    echo "  sudo chown -R \"$(whoami)\" \"${MINIKUBE_DIR}\"" >&2
    echo "  chmod -R u+rwX \"${MINIKUBE_DIR}\"" >&2
    exit 1
  fi
else
  if ! (mkdir -p "${MINIKUBE_DIR}" >/dev/null 2>&1 && touch "${MINIKUBE_DIR}/.write_test" >/dev/null 2>&1 && rm -f "${MINIKUBE_DIR}/.write_test" >/dev/null 2>&1); then
    echo "Minikube directory is not writable: ${MINIKUBE_DIR}" >&2
    echo "Fix ownership/permissions, then retry:" >&2
    echo "  sudo chown -R \"$(whoami)\" \"${MINIKUBE_DIR}\"" >&2
    echo "  chmod -R u+rwX \"${MINIKUBE_DIR}\"" >&2
    exit 1
  fi
fi

check_context
check_minikube
check_images

if [[ "${SKIP_LOAD}" != "true" ]]; then
  load_images
fi

if [[ "${SKIP_HELM}" == "true" ]]; then
  echo
  echo "Minikube images are ready for tag ${IMAGE_TAG}."
  echo "Run Helm separately with:"
  echo "  helm upgrade --install ${RELEASE_NAME} ${CHART_DIR} --namespace ${NAMESPACE} --create-namespace --set-string global.image.tag=${IMAGE_TAG}"
  exit 0
fi

echo "Applying Helm release ${RELEASE_NAME} in namespace ${NAMESPACE}..."
helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set-string global.image.tag="${IMAGE_TAG}"

rollout_apps

echo
echo "Minikube deployment is ready."
echo "Profile: ${MINIKUBE_PROFILE}"
echo "Image tag: ${IMAGE_TAG}"
kubectl get pods -n "${NAMESPACE}" -o wide
