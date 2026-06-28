#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${ROOT_DIR}/infrastructure/helm/federated-fraud-detection"
source "${ROOT_DIR}/scripts/deploy_common.sh"

RELEASE_NAME="${RELEASE_NAME:-federated-fraud}"
NAMESPACE="${NAMESPACE:-default}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-minikube}"
SKIP_LOAD=false
SKIP_HELM=false

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

check_minikube() {
  if ! minikube -p "${MINIKUBE_PROFILE}" status >/dev/null 2>&1; then
    echo "Minikube profile '${MINIKUBE_PROFILE}' is not running." >&2
    echo "Start it first, for example: minikube start -p ${MINIKUBE_PROFILE}" >&2
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

mapfile -t APP_DEPLOYMENTS < <(project_app_deployments)
mapfile -t IMAGES < <(project_tagged_images "${IMAGE_TAG}")

require_cmd docker
require_cmd kubectl
require_cmd helm
require_cmd minikube

MINIKUBE_DIR="${HOME}/.minikube"
MINIKUBE_PROFILE_DIR="${MINIKUBE_DIR}/profiles/${MINIKUBE_PROFILE}"

if [[ -d "${MINIKUBE_PROFILE_DIR}" ]]; then
  if [[ ! -w "${MINIKUBE_PROFILE_DIR}" ]]; then
    echo "Minikube profile directory is not writable: ${MINIKUBE_PROFILE_DIR}" >&2
    echo "Fix ownership/permissions, then retry:" >&2
    echo "  sudo chown -R \"$(whoami)\" \"${MINIKUBE_DIR}\"" >&2
    echo "  chmod -R u+rwX \"${MINIKUBE_DIR}\"" >&2
    exit 1
  fi
else
  if [[ ! -d "${MINIKUBE_DIR}" ]] && ! mkdir -p "${MINIKUBE_DIR}" >/dev/null 2>&1; then
    echo "Minikube directory is not writable: ${MINIKUBE_DIR}" >&2
    echo "Fix ownership/permissions, then retry:" >&2
    echo "  sudo chown -R \"$(whoami)\" \"${MINIKUBE_DIR}\"" >&2
    echo "  chmod -R u+rwX \"${MINIKUBE_DIR}\"" >&2
    exit 1
  fi

  if [[ ! -w "${MINIKUBE_DIR}" ]]; then
    echo "Minikube directory is not writable: ${MINIKUBE_DIR}" >&2
    echo "Fix ownership/permissions, then retry:" >&2
    echo "  sudo chown -R \"$(whoami)\" \"${MINIKUBE_DIR}\"" >&2
    echo "  chmod -R u+rwX \"${MINIKUBE_DIR}\"" >&2
    exit 1
  fi
fi

ensure_expected_context "${EXPECTED_CONTEXT}" \
  "Run 'kubectl config use-context ${EXPECTED_CONTEXT}' or override EXPECTED_CONTEXT intentionally."
check_minikube
verify_local_images "Build the missing images first, for example with scripts/build_all_images.sh." "${IMAGES[@]}"

if [[ "${IMAGE_TAG}" == "latest" ]]; then
  echo "Warning: deploying tag 'latest' can leave minikube on stale cached app images." >&2
  echo "Recommended local path: bash scripts/local_minikube_release.sh" >&2
fi

if [[ "${SKIP_LOAD}" != "true" ]]; then
  load_images
fi

if [[ "${SKIP_HELM}" == "true" ]]; then
  print_helm_followup \
    "Minikube images are ready for tag ${IMAGE_TAG}." \
    "helm upgrade --install ${RELEASE_NAME} ${CHART_DIR} --namespace ${NAMESPACE} --create-namespace --set-string global.image.tag=${IMAGE_TAG}"
  exit 0
fi

echo "Applying Helm release ${RELEASE_NAME} in namespace ${NAMESPACE}..."
helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set-string global.image.tag="${IMAGE_TAG}"

rollout_deployments "${NAMESPACE}" "180s" "${APP_DEPLOYMENTS[@]}"

print_deployment_summary \
  "Minikube deployment is ready." \
  "Profile" \
  "${MINIKUBE_PROFILE}" \
  "${IMAGE_TAG}" \
  "${NAMESPACE}"
