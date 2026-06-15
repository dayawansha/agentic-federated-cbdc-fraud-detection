# agentic-federated-cbdc-fraud-detection

## Project Scope

This repository contains an **MSc research prototype** for privacy-preserving fraud detection in CBDC-like payment networks using:

- federated learning orchestration across a central coordinator domain and bank-node domain
- graph neural network training on Elliptic++-derived transaction graph data
- privacy controls including differential privacy utilities, encrypted update transport, and protected update validation
- agentic coordination using LangGraph-based workflows, policy-aware gating, and suspicious-update screening
- operational fraud monitoring through Neo4j, Kafka-backed alerts, and a React dashboard

## Current Implementation

The current implementation is:

- **multi-bank extensible by architecture**
- **validated with one active bank node in the current runtime setup**
- **REST-based for the federated control plane**
- **Kafka-based for transaction and alert event streams**
- **PostgreSQL-backed for policy and model metadata**
- **local-disk backed for model artifact storage**

For dissertation-safe wording and detailed alignment between the target design and the working prototype, use:

- [Technical Design](doc/TECHNICAL-DESIGN.md)
- [Development Status](doc/status/devStatus.md)
- [Development Plan](doc/status/devPlan.md)

## Recommended Local Kubernetes

Use `minikube` as the primary local Kubernetes environment for this repo.

Build and deploy with the local release helper so each minikube rollout gets a fresh image tag:

```bash
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
bash scripts/local_minikube_release.sh --profile minikube
```

This path generates a unique local tag, builds the local images, loads them into `minikube`, deploys the Helm release, and records the active release metadata in `.local-state/minikube-release.env`.

If you need to reuse an explicit tag:

```bash
bash scripts/local_minikube_release.sh --tag local-manual-001 --profile minikube
```

To open the dashboard after deployment:

```bash
kubectl port-forward svc/fraud-dashboard 3000:3000
```

Then browse to `http://127.0.0.1:3000`.

The dashboard now proxies its own upstream API and WebSocket requests, so you do not need separate localhost port-forwards for `local-agent`, `transaction-graph`, or `alerting` just to use the UI.

To populate the dashboard with repeatable demo graph and alert data after deployment:

```bash
bash scripts/bootstrap_dashboard_demo_data.sh
```

This helper script:
- creates `fraud.alerts` if needed
- loads processed transaction data into `transaction-graph`
- publishes five demo fraud alerts through Kafka
- verifies the dashboard proxy endpoints return non-empty data
- can be rerun safely without inflating the same seeded transactions or alert IDs

For the full dashboard demo lifecycle:

```bash
bash scripts/demo_dashboard_lifecycle.sh full
```

For a single all-in-one local runtime helper that starts `minikube` if needed, builds images, deploys the full stack, starts port-forwards for the main services, bootstraps demo data, runs post-deploy health checks, and triggers the federated E2E test:

```bash
bash scripts/all_in_one_minikube.sh up --start-minikube
```

Useful follow-up commands:

```bash
bash scripts/all_in_one_minikube.sh status
bash scripts/all_in_one_minikube.sh down
```

Optional flags:

```bash
bash scripts/all_in_one_minikube.sh up --start-minikube --skip-seed
bash scripts/all_in_one_minikube.sh up --start-minikube --skip-health-checks --skip-e2e
```

Other modes:
- `bash scripts/demo_dashboard_lifecycle.sh reset`
- `bash scripts/demo_dashboard_lifecycle.sh seed`
- `bash scripts/demo_dashboard_lifecycle.sh verify`

Optional local proof helper:

```bash
bash scripts/ci_dashboard_smoke.sh
```

This smoke path still exists as a reusable reference, but it is not required for the normal local development workflow.

It:
- ensures `minikube` is running
- builds and deploys the current image tag unless you skip those phases
- proves the dashboard lifecycle automatically with `reset -> seed -> verify`

## Alternative Local Path

If you still need Docker Desktop, the repo also includes [scripts/deploy_docker_desktop.sh](scripts/deploy_docker_desktop.sh).

See [doc/DEPLOYMENT-GUIDE.md](doc/DEPLOYMENT-GUIDE.md) for the full build and deployment flow.
