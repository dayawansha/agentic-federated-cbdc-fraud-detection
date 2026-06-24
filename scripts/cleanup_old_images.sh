#!/bin/bash

# This script removes all old Docker images related to this project (tag != latest)
# from both the host Docker daemon and the containerd registry inside the Kubernetes worker node.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=== 1. Cleaning Host Docker Images ==="
if command -v docker >/dev/null 2>&1; then
  # List matching images for visibility
  docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | grep "dusman/federated-fraud-" || true
  
  # Delete non-latest images safely
  host_images=$(docker images --format "{{.Repository}}:{{.Tag}}=={{.ID}}" | grep "dusman/federated-fraud-" || true)
  if [[ -n "${host_images}" ]]; then
    for line in ${host_images}; do
      image_name="${line%%==*}"
      image_id="${line##*==}"
      tag="${image_name##*:}"
      
      if [[ "${tag}" != "latest" ]]; then
        echo "Removing host image: ${image_name} (${image_id})"
        docker rmi -f "${image_name}" || docker rmi -f "${image_id}" || true
      fi
    done
  else
    echo "No matching images found on host."
  fi
else
  echo "Docker command not found on host."
fi

echo
echo "=== 2. Cleaning Kubernetes Node Containerd Images ==="
if command -v docker >/dev/null 2>&1; then
  nodes=$(docker ps --format "{{.Names}}" | grep "^desktop-worker" || true)
  if [[ -z "${nodes}" ]]; then
    nodes=$(docker ps --format "{{.Names}}" | grep -E "worker|control-plane" || true)
  fi

  for node in ${nodes}; do
    echo "Processing node: ${node}..."
    if ! docker exec "${node}" echo "checking containerd..." >/dev/null 2>&1; then
      echo "Warning: Node ${node} is not accessible via docker exec (overlay2 or VM issues). Skipping containerd image pruning on this node."
      continue
    fi
    
    # List and remove non-latest images in k8s.io namespace safely
    k8s_images=$(docker exec "${node}" ctr -n k8s.io images list -q | grep "dusman/federated-fraud-" || true)
    if [[ -n "${k8s_images}" ]]; then
      for image in ${k8s_images}; do
        tag="${image##*:}"
        if [[ "${tag}" != "latest" ]]; then
          echo "  Removing image inside ${node}: ${image}"
          docker exec "${node}" ctr -n k8s.io images remove "${image}" || true
        fi
      done
    else
      echo "  No matching images inside containerd on ${node}."
    fi
  done
else
  echo "Docker command not found on host."
fi

echo
echo "=== Cleanup completed ==="
