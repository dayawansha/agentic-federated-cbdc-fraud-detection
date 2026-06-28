# Scripts

This folder contains helper scripts for local Docker Compose workflows, image management, Kubernetes deployment, demo-data bootstrapping, and validation utilities.

## How To Read This Folder

- Shell scripts (`.sh`) are mainly for build, deploy, reset, and verification workflows.
- Python utilities (`.py`) are mainly for API-driven test or reporting tasks.
- Some scripts are standalone entrypoints.
- Some scripts are support utilities used by other scripts and are not usually run directly.

## Quick Groups

### Compose Rebuild Helpers

- `rebuild_service_clean.sh`
  - Cleanly rebuilds one or more Docker Compose services.
  - Removes the current container for the selected service, deletes its local Compose-built image, then rebuilds and restarts it.
  - Useful after changing code in a single service when you do not want to keep the old local image.

- `rebuild_all_clean.sh`
  - Cleanly rebuilds the full Docker Compose stack.
  - Runs `docker compose down --remove-orphans --rmi local` and then rebuilds the stack.
  - Keeps volumes intact, so database data is preserved.

### Image Build And Cleanup

- `build_all_images.sh`
  - Builds all project application images with a chosen Docker tag.
  - Targets the manually tagged images used by the Helm and Kubernetes workflows, such as `dusman/federated-fraud-local-agent:<tag>`.
  - Useful before deploying to Minikube or Docker Desktop Kubernetes.

- `verify_images.sh`
  - Checks whether the expected tagged application images exist locally in Docker.
  - Prints which images are present, which are missing, and the image sizes for found images.
  - Useful as a quick pre-deployment sanity check.

- `cleanup_old_images.sh`
  - Removes old tagged project images from the host Docker daemon and also attempts to remove them from local Kubernetes node containerd storage.
  - Keeps images tagged `latest` and removes non-`latest` images matching `dusman/federated-fraud-*`.
  - Useful for cleaning stale Kubernetes-oriented image tags, not for Compose-only cleanup.

### Minikube And Local Kubernetes Deployment

- `deploy_common.sh`
  - Shared helper library for Kubernetes-oriented deployment scripts.
  - Provides reusable functions for required-command checks, tagged image list generation, local image verification, context guards, deployment rollout waiting, Helm follow-up guidance, and deployment summary output.
  - Usually sourced by deployment scripts rather than run directly.

- `minikube_release_common.sh`
  - Shared helper library for Minikube-oriented release workflows.
  - Provides reusable functions for local image tag generation plus env-style state file writing, loading, and printing.
  - Usually sourced by `local_minikube_release.sh` and `all_in_one_minikube.sh` rather than run directly.

- `deploy_minikube.sh`
  - Loads prebuilt tagged images into a Minikube profile and applies the Helm release.
  - Uses `deploy_common.sh` for image verification, rollout waiting, and deployment list reuse.
  - Verifies Minikube context, checks image availability, optionally skips image loading or Helm deployment, and waits for deployments to roll out.
  - Useful after building images for a Minikube-based local cluster.

- `deploy_docker_desktop.sh`
  - Imports prebuilt tagged images into the Docker Desktop Kubernetes node container runtime and applies the Helm release using Docker Desktop-specific values.
  - Uses `deploy_common.sh` for image verification, rollout waiting, and deployment list reuse.
  - Labels the runtime node, imports images via `ctr`, optionally skips Helm, and waits for app deployments.
  - Useful when using Docker Desktop's Kubernetes instead of Minikube.

- `local_minikube_release.sh`
  - Creates a deterministic local Minikube release using a generated or explicit image tag.
  - Can build all images, deploy them to Minikube, and record release metadata in `.local-state/minikube-release.env`.
  - Shares the deployment helper module used by the Minikube deploy path and the Minikube release helper for tag/state handling.
  - Useful when you want a fresh unique local release tag to avoid stale cached images.

- `all_in_one_minikube.sh`
  - End-to-end Minikube workflow wrapper.
  - Can start Minikube, resolve a release tag, build and deploy the stack, start local port-forwards, seed demo data, run health checks, and run the federated E2E test.
  - Shares the Minikube release helper for tag/state handling and the common deploy helper for command and context checks.
  - Supports `up`, `down`, and `status`.
  - Useful when you want one command to bring up the full local Minikube environment.

### Dashboard Demo Data And Lifecycle

- `dashboard_demo_common.sh`
  - Shared helper library for the dashboard demo scripts.
  - Provides reusable functions for port-forwarding, Kafka topic creation, Neo4j reset, alerting restart, seeding graph data, publishing demo alerts, and dashboard verification.
  - Usually sourced by other scripts rather than run directly.

- `demo_dashboard_lifecycle.sh`
  - Primary dashboard lifecycle entrypoint.
  - Implements `full`, `reset`, `seed`, and `verify` directly against `dashboard_demo_common.sh`.
  - This is the only supported command surface for demo reset/seed/verify workflows.

- `ci_dashboard_smoke.sh`
  - CI-style smoke test for the dashboard lifecycle on Minikube.
  - Reuses `deploy_common.sh` for command checks, deployment list reuse, and context validation.
  - Can start Minikube, build images, deploy the release, then run the dashboard lifecycle flow and collect failure context if something breaks.
  - Useful for automated or repeatable end-to-end smoke checks.

### Test And Data Utilities

- `e2e_fl_test.py`
  - Runs a basic end-to-end federated learning test against locally reachable services.
  - Checks service health, starts a coordinator round, and optionally copies model artifacts from the model-registry pod back to the host.
  - Useful after port-forwarding or exposing the core services locally.

- `load_transaction_graph_processed.py`
  - Loads a controlled subset of processed training data into `transaction-graph` via its REST API.
  - Reads the processed nodes and edges CSV files, derives transaction payloads, and inserts them through `POST /transactions`.
  - Useful for bootstrapping demo or test graph data.

- `privacy_evaluation_report.py`
  - Calls the privacy-layer evaluation APIs and prints a privacy report.
  - Supports single comparison mode using raw/protected/encrypted payloads and sweep mode across multiple noise multipliers.
  - Useful for analyzing privacy-utility tradeoffs after privacy-layer changes.

## Typical Workflows

### After Changing One Compose Service

```bash
scripts/rebuild_service_clean.sh local-agent
```

### After Changing Many Compose Services

```bash
scripts/rebuild_all_clean.sh
```

### Build And Deploy To Minikube With A Fresh Tag

```bash
bash scripts/local_minikube_release.sh
```

### Bring Up A Full Minikube Demo Environment

```bash
bash scripts/all_in_one_minikube.sh up --start-minikube
```

### Reset And Reseed Dashboard Demo Data

```bash
bash scripts/demo_dashboard_lifecycle.sh reset
bash scripts/demo_dashboard_lifecycle.sh seed
```

## Cleanup Plan

### Phase 1: Safe Consolidation

- Completed: move dashboard `reset`, `seed`, and `verify` logic into `demo_dashboard_lifecycle.sh`.
- Completed: retire the older dashboard wrapper scripts after downstream references were updated.
- Goal: reduce duplicated dashboard logic without breaking existing commands or docs immediately.

### Phase 2: Dashboard Surface Cleanup

- Completed: update docs and automation to prefer `demo_dashboard_lifecycle.sh`.
- Completed: remove the retired dashboard wrapper scripts so only one dashboard entrypoint remains.

### Phase 3: Deploy Script Refactor

- Completed: extract `deploy_common.sh` for shared deployment helpers.
- Completed: move shared image list generation, local image verification, context guards, rollout waiting, Helm follow-up output, and deployment summary output into the shared helper.
- Remaining candidates:
  - common option parsing patterns
  - stronger reuse between `local_minikube_release.sh` and `all_in_one_minikube.sh`

### Phase 3.5: Minikube Workflow Reuse

- Completed: extract `minikube_release_common.sh` for shared local tag generation and env-style release-state writing.
- Completed: use the shared Minikube helper in `local_minikube_release.sh` and `all_in_one_minikube.sh`.
- Completed: reuse the shared Minikube helper for env-style state/status printing.
- Remaining candidates:
  - shared option parsing for Minikube workflow entrypoints, if it can stay simple and Bash-compatible on macOS
  - possible shared status/reporting helpers for `.local-state` files

### Phase 4: High-Level Workflow Simplification

- Completed: align `ci_dashboard_smoke.sh` with `deploy_common.sh` for command checks, deployment list reuse, and context validation.
- Reduce overlap between:
  - `all_in_one_minikube.sh`
  - `ci_dashboard_smoke.sh`
  - `demo_dashboard_lifecycle.sh`
- Goal: keep one orchestration path for local operator flows and one for CI-oriented smoke validation.

### Phase 5: Naming And Scope Cleanup

- Clarify that `cleanup_old_images.sh` is for tagged Kubernetes image cleanup, not Compose local-image rebuild workflows.
- Keep Compose cleanup centered on:
  - `rebuild_service_clean.sh`
  - `rebuild_all_clean.sh`

## Notes

- Compose cleanup scripts work against `infrastructure/docker-compose.yml`.
- Kubernetes deployment scripts expect the Helm chart under `infrastructure/helm/federated-fraud-detection`.
- Demo scripts assume the related services are already deployed and reachable through Kubernetes resources and port-forwards.
- Image-tag scripts mostly target the manually tagged `dusman/federated-fraud-*` images used for Kubernetes workflows.
