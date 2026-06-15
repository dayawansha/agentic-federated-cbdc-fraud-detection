#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-latest}"

SERVICES=(
  "dusman/federated-fraud-agentic-coordinator|./central-coordinator/agentic-coordinator/Dockerfile"
  "dusman/federated-fraud-secure-aggregator|./central-coordinator/secure-aggregator/Dockerfile"
  "dusman/federated-fraud-policy-manager|./central-coordinator/policy-manager/Dockerfile"
  "dusman/federated-fraud-model-registry|./central-coordinator/model-registry/Dockerfile"
  "dusman/federated-fraud-local-agent|./bank-node/local-agent/Dockerfile"
  "dusman/federated-fraud-local-gnn|./bank-node/local-gnn-model/Dockerfile"
  "dusman/federated-fraud-privacy-layer|./bank-node/privacy-layer/Dockerfile"
  "dusman/federated-fraud-transaction-graph|./bank-node/transaction-graph/Dockerfile"
  "dusman/federated-fraud-alerting|./bank-node/alerting/Dockerfile"
  "dusman/federated-fraud-fraud-dashboard|./bank-node/fraud-dashboard/Dockerfile"
)

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --tag <tag>      Docker image tag to build (default: ${IMAGE_TAG})
  --help           Show this help message

Environment:
  IMAGE_TAG        Same as --tag
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      IMAGE_TAG="$2"
      shift 2
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

cd "${ROOT_DIR}"

for service in "${SERVICES[@]}"; do
  image="${service%%|*}"
  dockerfile="${service##*|}"
  echo "Building ${image}:${IMAGE_TAG}..."
  docker build -t "${image}:${IMAGE_TAG}" -f "${dockerfile}" .
done

echo
echo "Built ${#SERVICES[@]} images with tag ${IMAGE_TAG}."
