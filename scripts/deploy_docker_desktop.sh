#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${ROOT_DIR}/infrastructure/helm/federated-fraud-detection"
VALUES_FILE="${CHART_DIR}/values.local-docker-desktop.yaml"
source "${ROOT_DIR}/scripts/deploy_common.sh"

RELEASE_NAME="${RELEASE_NAME:-federated-fraud}"
NAMESPACE="${NAMESPACE:-default}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
RUNTIME_NODE="${RUNTIME_NODE:-}"
LABEL_KEY="app-runtime"
LABEL_VALUE="true"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-docker-desktop}"
SKIP_HELM=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --tag <tag>          Docker image tag to import and deploy
  --node <node>        Kubernetes node and matching Docker container to host app images
  --namespace <ns>     Helm release namespace (default: ${NAMESPACE})
  --release <name>     Helm release name (default: ${RELEASE_NAME})
  --skip-helm          Only label/import images; do not run Helm upgrade
  --help               Show this help message

Environment:
  IMAGE_TAG            Same as --tag
  RUNTIME_NODE         Same as --node
  EXPECTED_CONTEXT     Kubernetes context guard (default: docker-desktop)
EOF
}

detect_runtime_node() {
  local node=""

  if [[ -n "${RUNTIME_NODE}" ]]; then
    echo "${RUNTIME_NODE}"
    return 0
  fi

  node="$(kubectl get nodes -o name | sed 's#node/##' | grep '^desktop-worker' | head -n 1 || true)"
  if [[ -z "${node}" ]]; then
    node="$(kubectl get nodes -o name | sed 's#node/##' | grep -v 'control-plane' | head -n 1 || true)"
  fi
  if [[ -z "${node}" ]]; then
    node="$(kubectl get nodes -o name | sed 's#node/##' | head -n 1 || true)"
  fi
  if [[ -z "${node}" ]]; then
    echo "Unable to detect a Kubernetes node to host local app images." >&2
    exit 1
  fi

  echo "${node}"
}

import_images() {
  local runtime_node="$1"
  local image

  for image in "${IMAGES[@]}"; do
    echo "Importing ${image} into ${runtime_node}..."
    docker save "${image}" | docker exec -i "${runtime_node}" ctr -n k8s.io images import -
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --node)
      RUNTIME_NODE="$2"
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

mapfile -t APP_DEPLOYMENTS < <(project_app_deployments)
mapfile -t IMAGES < <(project_tagged_images "${IMAGE_TAG}")

require_cmd docker
require_cmd kubectl
require_cmd helm

ensure_expected_context "${EXPECTED_CONTEXT}" \
  "Set EXPECTED_CONTEXT to override this guard if you intentionally want another local cluster."
verify_local_images "Build the missing images first, then rerun this script." "${IMAGES[@]}"

RUNTIME_NODE="$(detect_runtime_node)"

if ! docker inspect "${RUNTIME_NODE}" >/dev/null 2>&1; then
  echo "Docker container '${RUNTIME_NODE}' was not found. Expected the Docker Desktop node container to match the Kubernetes node name." >&2
  exit 1
fi

echo "Labeling ${RUNTIME_NODE} with ${LABEL_KEY}=${LABEL_VALUE}..."
kubectl label node "${RUNTIME_NODE}" "${LABEL_KEY}=${LABEL_VALUE}" --overwrite

import_images "${RUNTIME_NODE}"

if [[ "${SKIP_HELM}" == "true" ]]; then
  print_helm_followup \
    "Images loaded into ${RUNTIME_NODE}." \
    "helm upgrade --install ${RELEASE_NAME} ${CHART_DIR} --namespace ${NAMESPACE} --create-namespace -f ${CHART_DIR}/values.yaml -f ${VALUES_FILE} --set-string global.image.tag=${IMAGE_TAG}"
  exit 0
fi

echo "Applying Helm release ${RELEASE_NAME} in namespace ${NAMESPACE}..."
helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  -f "${CHART_DIR}/values.yaml" \
  -f "${VALUES_FILE}" \
  --set-string global.image.tag="${IMAGE_TAG}"

rollout_deployments "${NAMESPACE}" "180s" "${APP_DEPLOYMENTS[@]}"

print_deployment_summary \
  "Docker Desktop local-cluster deployment is ready." \
  "Runtime node" \
  "${RUNTIME_NODE}" \
  "${IMAGE_TAG}" \
  "${NAMESPACE}"
