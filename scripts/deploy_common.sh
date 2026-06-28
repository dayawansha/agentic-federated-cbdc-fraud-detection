#!/bin/bash

# Shared helper functions for Kubernetes-oriented deployment scripts.

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

project_app_deployments() {
  cat <<'EOF'
agentic-coordinator
federated-model-aggregator
policy-manager
model-registry
local-agent
local-gnn
privacy-layer
transaction-graph
alerting
fraud-dashboard
EOF
}

project_tagged_images() {
  local image_tag="$1"
  local image_prefix="${IMAGE_PREFIX:-dusman/federated-fraud}"

  if [[ -z "${image_tag}" ]]; then
    echo "project_tagged_images requires a non-empty image tag." >&2
    return 1
  fi

  cat <<EOF
${image_prefix}-agentic-coordinator:${image_tag}
${image_prefix}-federated-model-aggregator:${image_tag}
${image_prefix}-policy-manager:${image_tag}
${image_prefix}-model-registry:${image_tag}
${image_prefix}-local-agent:${image_tag}
${image_prefix}-local-gnn:${image_tag}
${image_prefix}-privacy-layer:${image_tag}
${image_prefix}-transaction-graph:${image_tag}
${image_prefix}-alerting:${image_tag}
${image_prefix}-fraud-dashboard:${image_tag}
EOF
}

ensure_expected_context() {
  local expected_context="$1"
  local guidance="${2:-}"
  local current_context

  current_context="$(kubectl config current-context)"
  if [[ "${current_context}" != "${expected_context}" ]]; then
    echo "Current kubectl context is '${current_context}', expected '${expected_context}'." >&2
    if [[ -n "${guidance}" ]]; then
      echo "${guidance}" >&2
    fi
    return 1
  fi
}

verify_local_images() {
  local build_hint="$1"
  shift

  local missing=0
  local image
  for image in "$@"; do
    if ! docker image inspect "${image}" >/dev/null 2>&1; then
      echo "Missing local image: ${image}" >&2
      missing=1
    fi
  done

  if [[ "${missing}" -ne 0 ]]; then
    if [[ -n "${build_hint}" ]]; then
      echo "${build_hint}" >&2
    fi
    return 1
  fi
}

rollout_deployments() {
  local namespace="$1"
  local timeout="${2:-180s}"
  shift 2

  local deployment
  for deployment in "$@"; do
    echo "Waiting for deployment/${deployment}..."
    kubectl rollout status "deployment/${deployment}" -n "${namespace}" --timeout="${timeout}"
  done
}

print_helm_followup() {
  local status_message="$1"
  local helm_command="$2"

  echo
  echo "${status_message}"
  echo "Run Helm separately with:"
  echo "  ${helm_command}"
}

print_deployment_summary() {
  local title="$1"
  local detail_label="$2"
  local detail_value="$3"
  local image_tag="$4"
  local namespace="$5"

  echo
  echo "${title}"
  if [[ -n "${detail_label}" ]]; then
    echo "${detail_label}: ${detail_value}"
  fi
  echo "Image tag: ${image_tag}"
  kubectl get pods -n "${namespace}" -o wide
}
