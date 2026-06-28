#!/bin/bash

# Shared helper functions for Minikube-oriented release workflows.

generate_local_release_tag() {
  local tag_prefix="${1:-local}"
  printf "%s-%s" "${tag_prefix}" "$(date +%Y%m%d-%H%M%S)"
}

write_env_state_file() {
  local target_file="$1"
  shift

  mkdir -p "$(dirname "${target_file}")"

  {
    local entry
    for entry in "$@"; do
      echo "${entry}"
    done
  } > "${target_file}"
}

print_env_state_file() {
  local target_file="$1"
  local missing_message="${2:-No state metadata found.}"

  if [[ -f "${target_file}" ]]; then
    cat "${target_file}"
  else
    echo "${missing_message}"
  fi
}

load_env_state_file() {
  local target_file="$1"

  if [[ ! -f "${target_file}" ]]; then
    return 1
  fi

  # State files are written by project scripts as simple KEY=VALUE lines.
  # shellcheck disable=SC1090
  source "${target_file}"
}
