#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${ROOT_DIR}/infrastructure"
NO_DEPS=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] <service> [service...]

Cleanly rebuild one or more Docker Compose services by:
  1. Removing the existing service container
  2. Deleting the current local image used by that service
  3. Rebuilding and restarting the service

Options:
  --no-deps        Rebuild only the specified service(s) without starting dependencies
  --help, -h       Show this help message

Examples:
  $(basename "$0") local-agent
  $(basename "$0") --no-deps alerting fraud-dashboard
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

SERVICES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-deps)
      NO_DEPS=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      SERVICES+=("$1")
      shift
      ;;
  esac
done

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  echo "At least one Compose service name is required." >&2
  usage >&2
  exit 1
fi

require_cmd docker

cd "${COMPOSE_DIR}"

for service in "${SERVICES[@]}"; do
  echo
  echo "=== Rebuilding service: ${service} ==="

  if ! docker compose config --services | grep -Fx "${service}" >/dev/null 2>&1; then
    echo "Unknown Compose service: ${service}" >&2
    exit 1
  fi

  container_id="$(docker compose ps -q "${service}" || true)"
  if [[ -n "${container_id}" ]]; then
    echo "Removing existing container for ${service}..."
    docker compose rm -sf "${service}"
  else
    echo "No existing container found for ${service}."
  fi

  image_ids=()
  while IFS= read -r image_id; do
    [[ -n "${image_id}" ]] || continue
    image_ids+=("${image_id}")
  done <<EOF
$(docker compose images -q "${service}" | awk 'NF' | sort -u)
EOF
  if [[ ${#image_ids[@]} -gt 0 ]]; then
    echo "Removing current local image(s) for ${service}..."
    docker image rm -f "${image_ids[@]}"
  else
    echo "No existing local image found for ${service}."
  fi

  echo "Rebuilding and restarting ${service}..."
  if [[ "${NO_DEPS}" == "true" ]]; then
    docker compose up -d --build --no-deps "${service}"
  else
    docker compose up -d --build "${service}"
  fi

  echo "Finished: ${service}"
done

echo
echo "Clean rebuild completed for: ${SERVICES[*]}"
