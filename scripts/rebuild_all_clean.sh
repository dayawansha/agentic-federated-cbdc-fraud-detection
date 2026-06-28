#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${ROOT_DIR}/infrastructure"
NO_START=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Cleanly rebuild the full Docker Compose stack by:
  1. Stopping and removing Compose containers
  2. Deleting locally built Compose images
  3. Rebuilding the stack

Options:
  --no-start       Build images only; do not start the stack
  --help, -h       Show this help message

Examples:
  $(basename "$0")
  $(basename "$0") --no-start
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
    --no-start)
      NO_START=true
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

cd "${COMPOSE_DIR}"

echo "Stopping and removing existing Compose containers..."
docker compose down --remove-orphans --rmi local

if [[ "${NO_START}" == "true" ]]; then
  echo "Rebuilding full stack without starting containers..."
  docker compose build
else
  echo "Rebuilding and starting full stack..."
  docker compose up -d --build
fi

echo
echo "Clean full-stack rebuild completed."
