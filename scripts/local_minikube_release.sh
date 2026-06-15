#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${ROOT_DIR}/.local-state"
STATE_FILE="${STATE_DIR}/minikube-release.env"

TAG_PREFIX="${TAG_PREFIX:-local}"
IMAGE_TAG="${IMAGE_TAG:-}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-minikube}"
RELEASE_NAME="${RELEASE_NAME:-federated-fraud}"
NAMESPACE="${NAMESPACE:-default}"
SKIP_BUILD=false
SKIP_DEPLOY=false
PRINT_ONLY=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Creates a deterministic local minikube release using a unique image tag.

Options:
  --tag <tag>            Use an explicit Docker image tag
  --profile <name>       Minikube profile name (default: ${MINIKUBE_PROFILE})
  --namespace <ns>       Helm namespace (default: ${NAMESPACE})
  --release <name>       Helm release name (default: ${RELEASE_NAME})
  --skip-build           Reuse existing local images for the selected tag
  --skip-deploy          Skip minikube image load + Helm deploy
  --print-tag            Print the resolved tag and exit
  --help                 Show this help message

Environment:
  IMAGE_TAG              Same as --tag
  TAG_PREFIX             Auto-generated tag prefix (default: local)
  MINIKUBE_PROFILE       Same as --profile
  EXPECTED_CONTEXT       kubectl context guard (default: minikube)
EOF
}

generate_tag() {
  printf "%s-%s" "${TAG_PREFIX}" "$(date +%Y%m%d-%H%M%S)"
}

record_release_state() {
  mkdir -p "${STATE_DIR}"
  cat >"${STATE_FILE}" <<EOF
IMAGE_TAG=${IMAGE_TAG}
MINIKUBE_PROFILE=${MINIKUBE_PROFILE}
EXPECTED_CONTEXT=${EXPECTED_CONTEXT}
RELEASE_NAME=${RELEASE_NAME}
NAMESPACE=${NAMESPACE}
RELEASED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
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
    --print-tag)
      PRINT_ONLY=true
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

if [[ -z "${IMAGE_TAG}" ]]; then
  IMAGE_TAG="$(generate_tag)"
fi

if [[ "${PRINT_ONLY}" == "true" ]]; then
  echo "${IMAGE_TAG}"
  exit 0
fi

cd "${ROOT_DIR}"

echo "Resolved local release tag: ${IMAGE_TAG}"

if [[ "${SKIP_BUILD}" != "true" ]]; then
  bash scripts/build_all_images.sh --tag "${IMAGE_TAG}"
fi

if [[ "${SKIP_DEPLOY}" != "true" ]]; then
  EXPECTED_CONTEXT="${EXPECTED_CONTEXT}" \
    bash scripts/deploy_minikube.sh \
      --tag "${IMAGE_TAG}" \
      --profile "${MINIKUBE_PROFILE}" \
      --namespace "${NAMESPACE}" \
      --release "${RELEASE_NAME}"
fi

record_release_state

echo
echo "Local minikube release recorded at ${STATE_FILE}"
echo "Image tag: ${IMAGE_TAG}"
