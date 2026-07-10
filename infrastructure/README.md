# Infrastructure

This directory contains Infrastructure as Code (IaC) for the project.

## Contents

- **docker-compose.yml** - Local development environment
- **docker-compose.dev.yml** - Development overrides
- **kubernetes/** - Kubernetes manifests
- **helm/** - Helm charts for deployment

## Active Services & Containers

The following services run locally under the Docker Compose environment:

| Container Name | Service Name | Status | Mapped Ports | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `infrastructure-agentic-coordinator-1` | `agentic-coordinator` | **Up** | `8001 -> 8001` | Orchestrates LangGraph-based workflows |
| `infrastructure-alerting-1` | `alerting` | **Up** | `9005 -> 9005` | Checks CDC alerts |
| `infrastructure-federated-model-aggregator-1` | `federated-model-aggregator` | **Up** | `8002 -> 8002` | Aggregates GNN weights |
| `infrastructure-fraud-dashboard-1` | `fraud-dashboard` | **Up** | `3000 -> 3000` | Frontend dashboard for operators |
| `infrastructure-kafka-1` | `kafka` | **Up** | `9092 -> 9092` | Event streaming engine |
| `infrastructure-kafka-ui-1` | `kafka-ui` | **Up** | `18080 -> 8080` | Web UI for monitoring Kafka |
| `infrastructure-local-agent-1` | `local-agent` | **Up** | `9001 -> 9001` | Bank node controller |
| `infrastructure-local-gnn-1` | `local-gnn` | **Up** | `9002 -> 9002` | Runs PyTorch Geometric training |
| `infrastructure-model-registry-1` | `model-registry` | **Up** | `8004 -> 8004` | Manages ML models & artifacts |
| `infrastructure-neo4j-1` | `neo4j` | **Up** | `7474`, `7687` | Transaction database graph store |
| `infrastructure-policy-manager-1` | `policy-manager` | **Up** | `8003 -> 8003` | Validates privacy budget & constraints |
| `infrastructure-postgres-1` | `postgres` | **Up** | `5432 -> 5432` | Alert & metadata database |
| `infrastructure-privacy-layer-1` | `privacy-layer` | **Up** | `9003 -> 9003` | Implements Differential Privacy algorithms |
| `infrastructure-redis-1` | `redis` | **Up** | `6379 -> 6379` | Fast key-value store for session states |
| `infrastructure-redis-insight-1` | `redis-insight` | **Up** | `5540 -> 5540` | GUI for Redis databases |
| `infrastructure-transaction-graph-1` | `transaction-graph` | **Up** | `9004 -> 9004` | Indexes transaction pipelines |
| `infrastructure-zookeeper-1` | `zookeeper` | **Up** | internal (`2181`) | Manages Kafka cluster state |
