# Deployment & Operations Guide

This guide provides instructions for deploying and operating the Agentic Federated Learning Framework.

## 1. Local Development (Docker Compose)

The easiest way to run the entire stack locally is using Docker Compose.

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local scripts)
- At least 8GB RAM allocated to Docker

### Steps
1. Navigate to the infrastructure folder:
   ```bash
   cd infrastructure
   ```
2. Start the core services:
   ```bash
   docker-compose up -d
   ```
3. Verify services:
   ```bash
   docker ps
   ```

## 2. Kubernetes Deployment

### Prerequisites
- A running Kubernetes cluster
- For local development, `minikube` is the recommended path
- Helm v3 installed
- Docker installed (for building images)
- Docker Desktop running if `minikube` uses the `docker` driver

### Step 1: Build Microservice Images
Before deploying, you must build the images for each microservice. **You MUST run these commands from the PROJECT ROOT directory** (`agentic-federated-cbdc-fraud-detection`).

The build context is set to `.` (the current directory) so that the `shared/` folder can be included in the images. We use the `-f` flag to point to the specific `Dockerfile` for each service.

Use one shared image tag during a build/deploy cycle so the app-layer names stay aligned across Docker, Helm, and Kubernetes.

For the current validated local workflow, `latest` is the simplest choice:

```bash
export IMAGE_TAG=latest
```

Recommended helper:

```bash
bash scripts/build_all_images.sh --tag "${IMAGE_TAG}"
```

#### Build Optimizations
All Dockerfiles now include:
1. **Pip Cache Mount**: Uses `--mount=type=cache,target=/root/.cache/pip` to prevent re-downloading packages. This saves bandwidth and time.
2. **Long Timeouts**: All services use `PIP_DEFAULT_TIMEOUT=19000` to prevent timeout errors with large packages (like PyTorch).

#### Coordinator Domain
```bash
# Agentic Coordinator
docker build -t dusman/federated-fraud-agentic-coordinator:${IMAGE_TAG} -f ./central-coordinator/agentic-coordinator/Dockerfile .

# Secure Aggregator
docker build -t dusman/federated-fraud-secure-aggregator:${IMAGE_TAG} -f ./central-coordinator/secure-aggregator/Dockerfile .

# Policy Manager
docker build -t dusman/federated-fraud-policy-manager:${IMAGE_TAG} -f ./central-coordinator/policy-manager/Dockerfile .

# Model Registry
docker build -t dusman/federated-fraud-model-registry:${IMAGE_TAG} -f ./central-coordinator/model-registry/Dockerfile .
```

#### Bank Node Domain
```bash
# Local Agent
docker build -t dusman/federated-fraud-local-agent:${IMAGE_TAG} -f ./bank-node/local-agent/Dockerfile .

# Local GNN
docker build -t dusman/federated-fraud-local-gnn:${IMAGE_TAG} -f ./bank-node/local-gnn-model/Dockerfile .

# Privacy Layer
docker build -t dusman/federated-fraud-privacy-layer:${IMAGE_TAG} -f ./bank-node/privacy-layer/Dockerfile .

# Transaction Graph
docker build -t dusman/federated-fraud-transaction-graph:${IMAGE_TAG} -f ./bank-node/transaction-graph/Dockerfile .

# Alerting
docker build -t dusman/federated-fraud-alerting:${IMAGE_TAG} -f ./bank-node/alerting/Dockerfile .

# Fraud Dashboard
docker build -t dusman/federated-fraud-fraud-dashboard:${IMAGE_TAG} -f ./bank-node/fraud-dashboard/Dockerfile .
```

### Step 2: Recommended Local Kubernetes Path (Minikube)
`minikube` is the recommended local Kubernetes environment for this repo because it stays close to standard Kubernetes behavior and supports direct image loading without the Docker Desktop node-import workaround.

This repo has been validated with `minikube` using the `docker` driver and `containerd` inside the cluster node.

Start `minikube` if needed:

```bash
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
```

If you need to fully recreate the local cluster first:

```bash
minikube delete -p minikube
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
```

Then deploy with the repo helper:

```bash
bash scripts/deploy_minikube.sh --tag "${IMAGE_TAG}" --profile minikube
```

What this script does:

1. checks that the `minikube` profile is running
2. verifies the local images exist for the selected tag
3. loads those images with `minikube image load`
4. runs `helm upgrade --install`
5. waits for the application deployments to roll out

Recommended end-to-end local sequence:

```bash
export IMAGE_TAG=latest
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
bash scripts/build_all_images.sh --tag "${IMAGE_TAG}"
bash scripts/deploy_minikube.sh --tag "${IMAGE_TAG}" --profile minikube
```

Optional flags:

```bash
# Only load images into minikube
bash scripts/deploy_minikube.sh --tag "${IMAGE_TAG}" --skip-helm

# Skip image loading and only apply Helm
bash scripts/deploy_minikube.sh --tag "${IMAGE_TAG}" --skip-load
```

### Step 3: Alternative Local Path (Docker Desktop)
If you still want to use the local `docker-desktop` cluster, use the repo helper script. It makes the local-image workflow repeatable by:

1. labeling one Kubernetes node with `app-runtime=true`
2. importing the locally built app images into that node's container runtime
3. running Helm with the Docker Desktop override file so app deployments use `nodeSelector`

```bash
bash scripts/deploy_docker_desktop.sh --tag "${IMAGE_TAG}"
```

This script applies the Helm override file:

```text
infrastructure/helm/federated-fraud-detection/values.local-docker-desktop.yaml
```

That override enables the chart's local-cluster mode and pins app deployments to the labeled runtime node.

Optional flags:

```bash
# Use a specific Docker Desktop worker node
bash scripts/deploy_docker_desktop.sh --tag "${IMAGE_TAG}" --node desktop-worker

# Only import images and label the runtime node
bash scripts/deploy_docker_desktop.sh --tag "${IMAGE_TAG}" --skip-helm
```

### Step 4: Manual Image Loading (Other Local Clusters)
If using another local cluster, you still need to load the images into the cluster nodes:

```bash
# Example for Minikube
minikube image load dusman/federated-fraud-agentic-coordinator:${IMAGE_TAG}
minikube image load dusman/federated-fraud-secure-aggregator:${IMAGE_TAG}
minikube image load dusman/federated-fraud-policy-manager:${IMAGE_TAG}
minikube image load dusman/federated-fraud-model-registry:${IMAGE_TAG}
minikube image load dusman/federated-fraud-local-agent:${IMAGE_TAG}
minikube image load dusman/federated-fraud-local-gnn:${IMAGE_TAG}
minikube image load dusman/federated-fraud-privacy-layer:${IMAGE_TAG}
minikube image load dusman/federated-fraud-transaction-graph:${IMAGE_TAG}
minikube image load dusman/federated-fraud-alerting:${IMAGE_TAG}
minikube image load dusman/federated-fraud-fraud-dashboard:${IMAGE_TAG}
```

### Step 5: Install Via Helm
```bash
helm install federated-fraud ./infrastructure/helm/federated-fraud-detection
```

For `minikube` and Docker Desktop, the helper scripts already run the equivalent `helm upgrade --install` command.

### Step 6: Verify Deployment
```bash
kubectl get pods
```
If pods show `ImagePullBackOff`, ensure the image names and tag in `values.yaml` match your local builds.

For `minikube`, also verify:

```bash
minikube status -p minikube
kubectl get svc
kubectl get nodes
kubectl get pods -o wide
```

The validated healthy local result is that all application and infrastructure pods are `Running` on the single `minikube` node, including:
- `agentic-coordinator`
- `secure-aggregator`
- `policy-manager`
- `model-registry`
- `local-agent`
- `local-gnn`
- `privacy-layer`
- `transaction-graph`
- `alerting`
- `fraud-dashboard`
- `kafka`
- `kafka-ui`
- `neo4j`
- `postgres`
- `redis`
- `zookeeper`
- `prometheus`

### Step 7: Functional Smoke Checks
Check the two services that commonly need an extra look if they had startup retries:

```bash
kubectl logs deploy/model-registry --tail=100
kubectl logs deploy/policy-manager --tail=100
```

Forward key services for health and UI checks:

```bash
kubectl port-forward svc/agentic-coordinator 8001:8001
kubectl port-forward svc/transaction-graph 9004:9004
kubectl port-forward svc/alerting 9005:9005
kubectl port-forward svc/kafka-ui 8080:8080
kubectl port-forward svc/neo4j 7474:7474 7687:7687
```

Then validate:

```bash
curl http://localhost:8001/health
curl http://localhost:9004/health
curl http://localhost:9005/health
curl http://localhost:9004/accounts
```

Open these in the browser when needed:
- `http://localhost:8001/docs`
- `http://localhost:9004/docs`
- `http://localhost:9005/docs`
- `http://localhost:8080`
- `http://localhost:7474`

For the dashboard itself, a single port-forward is now enough because the dashboard proxies its upstream APIs inside the cluster:

```bash
kubectl port-forward svc/fraud-dashboard 3000:3000
```

Then open:
- `http://localhost:3000`

The dashboard now routes:
- `GET /api/local-agent/*`
- `GET /api/local-gnn/*`
- `GET /api/privacy-layer/*`
- `GET /api/transaction-graph/*`
- `GET /api/alerting/*`
- `GET /ws/alerts`
- `GET /kafka-ui/`

For Docker Desktop, also verify:

```bash
kubectl get nodes --show-labels | grep app-runtime
kubectl get pods -o wide
```

## 3. Monitoring & Observability

### Health Checks
Each microservice exposes a `/health` endpoint.

### Metrics (Prometheus/Grafana)
- **Training Latency**: Time taken for local GNN training.
- **Privacy Overhead**: Latency added by DP and Encryption.
- **Aggregation Convergence**: Global model accuracy over rounds.
- **System Health**: CPU/Memory usage per node.

## 4. Troubleshooting

### Data Pull Issues
If `txs_features.csv` or other data files are missing, ensure Git LFS is installed and run:
```bash
git lfs pull
```

### Kafka Connectivity
If services fail to connect to Kafka, verify the `KAFKA_BOOTSTRAP_SERVERS` environment variable in `docker-compose.yml`.

### REST Payload Size
Large model updates may increase request size and latency. Ensure reverse proxies and service limits are sized appropriately for JSON/base64 model-weight payloads.

### Minikube With Docker Driver
If `minikube start -p minikube` fails with Docker-related errors:

```bash
docker version
docker info
minikube status -p minikube
```

If the old cluster is stuck, clean it and recreate it:

```bash
minikube delete -p minikube
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
```

If Docker Desktop is not healthy, `minikube` with the `docker` driver will also fail because the cluster node itself runs as a Docker container.

If `minikube start` fails with `operation not permitted` under `~/.minikube` (for example when writing `~/.minikube/profiles/minikube/config.json`), fix the permissions and retry:

```bash
sudo chown -R "$(whoami)" ~/.minikube
chmod -R u+rwX ~/.minikube
minikube delete -p minikube
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
```
