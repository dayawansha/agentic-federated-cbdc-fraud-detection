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

## 2. Kubernetes Deployment (Production)

### Prerequisites
- A running Kubernetes cluster (Minikube, Kind, or Cloud-based)
- Helm v3 installed
- Docker installed (for building images)

### Step 1: Build Microservice Images
Before deploying, you must build the images for each microservice. From the **PROJECT ROOT** (`agentic-federated-cbdc-fraud-detection`), run the following commands using `-f` to specify the Dockerfile path:

#### Coordinator Domain
```bash
# Agentic Coordinator
docker build -t dusman/federated-fraud-agentic-coordinator:latest -f ./central-coordinator/agentic-coordinator/Dockerfile .

# Secure Aggregator
docker build -t dusman/federated-fraud-secure-aggregator:latest -f ./central-coordinator/secure-aggregator/Dockerfile .

# Policy Manager
docker build -t dusman/federated-fraud-policy-manager:latest -f ./central-coordinator/policy-manager/Dockerfile .

# Model Registry
docker build -t dusman/federated-fraud-model-registry:latest -f ./central-coordinator/model-registry/Dockerfile .
```

#### Bank Node Domain
```bash
# Local Agent
docker build -t dusman/federated-fraud-local-agent:latest -f ./bank-node/local-agent/Dockerfile .

# Local GNN Model
docker build -t dusman/federated-fraud-local-gnn:latest -f ./bank-node/local-gnn-model/Dockerfile .

# Privacy Layer
docker build -t dusman/federated-fraud-privacy-layer:latest -f ./bank-node/privacy-layer/Dockerfile .

# Transaction Graph
docker build -t dusman/federated-fraud-transaction-graph:latest -f ./bank-node/transaction-graph/Dockerfile .

# Alerting Service
docker build -t dusman/federated-fraud-alerting:latest -f ./bank-node/alerting/Dockerfile .

# Fraud Dashboard
docker build -t dusman/federated-fraud-fraud-dashboard:latest -f ./bank-node/fraud-dashboard/Dockerfile .
```

### Step 2: Load Images (Local Clusters)
If using **Minikube** or **Kind**, you must load the images into the cluster nodes:

```bash
# Example for Minikube
minikube image load dusman/federated-fraud-agentic-coordinator:latest
minikube image load dusman/federated-fraud-secure-aggregator:latest
minikube image load dusman/federated-fraud-policy-manager:latest
minikube image load dusman/federated-fraud-model-registry:latest
minikube image load dusman/federated-fraud-local-agent:latest
minikube image load dusman/federated-fraud-local-gnn:latest
minikube image load dusman/federated-fraud-privacy-layer:latest
minikube image load dusman/federated-fraud-transaction-graph:latest
minikube image load dusman/federated-fraud-alerting:latest
minikube image load dusman/federated-fraud-fraud-dashboard:latest
```

### Step 3: Install via Helm
```bash
helm install federated-fraud ./infrastructure/helm/federated-fraud-detection
```

### Step 4: Verify Deployment
```bash
kubectl get pods
```
If pods show `ImagePullBackOff`, ensure the image names in `values.yaml` match your local builds.

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

### gRPC Timeouts
Large model updates might cause gRPC timeouts. Ensure `GRPC_MAX_RECEIVE_MESSAGE_LENGTH` is configured correctly for model weight sizes.
