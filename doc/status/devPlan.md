# Development Plan
## Agentic Federated Learning Framework for CBDC Fraud Detection

**Version:** 2.0  
**Created:** February 2026  
**Updated:** February 2026  
**Status:** Planning Phase  
**Architecture:** Microservice Architecture

---

## 1. Architecture Overview

### 1.1 Microservice Architecture Principles

| Principle | Description |
|-----------|-------------|
| **Independent Deployment** | Each service has its own codebase and can be deployed independently |
| **Domain Grouping** | Services are grouped by domain (Coordinator / Bank Node) |
| **Communication Patterns** | Inter-node: Kafka (CDC); Intra-node: gRPC |
| **Technology Agnostic** | Each service can use different technologies as needed |
| **Loose Coupling** | Services communicate via well-defined APIs and events |

### 1.2 Service Communication Patterns

```mermaid
graph LR
    subgraph "Synchronous"
        HTTP[HTTP/REST]
        GRPC[gRPC]
    end
    
    subgraph "Asynchronous"
        SAGA[SAGA Pattern]
        CDC[Change Data Capture]
        KAFKA[Kafka Events]
    end
```

| Pattern | Use Case |
|---------|----------|
| **HTTP/REST** | CRUD operations, Dashboard APIs, External integrations |
| **gRPC** | High-performance inter-service calls, Model transfer |
| **SAGA** | Distributed transactions (e.g., FL training rounds) |
| **CDC** | Transaction streaming, Real-time data sync |

### 1.3 High-Level Architecture

```mermaid
graph TB
    subgraph "Central Coordinator Domain"
        AC[Agentic Coordinator<br/>Meta-Agent]
        SA[Secure Aggregator<br/>FedAvg/FedGNN]
        PM[Policy Manager<br/>Privacy + Governance]
        MR[Model Registry<br/>Versions + Metrics]
    end
    
    subgraph "Bank Node Domain (per Bank)"
        LA[Local Agent]
        LG[Local GNN Model]
        PL[Privacy Layer<br/>DP + Encryption]
        TG[Transaction Graph]
        FD[Fraud Dashboard<br/>Monitoring UI]
        AL[Alerting<br/>Email/Ticket]
    end
    
    subgraph "Infrastructure"
        KF[Apache Kafka]
        N4[Neo4j]
        PG[PostgreSQL]
        RD[Redis]
    end
    
    %% Inter-Node Communication (Bank <-> Central)
    LA <-->|Kafka/CDC| AC
    LA <-->|Kafka/CDC| SA
    
    %% Intra-Node Communication (Internal)
    AC <-->|gRPC| SA
    AC <-->|gRPC| PM
    SA <-->|gRPC| MR
    
    LA -->|gRPC| LG
    LA -->|gRPC| PL
    LG <-->|gRPC| TG
    FD <-->|gRPC| LA
    AL <-->|Kafka/CDC| TG
    
    TG --> KF
    TG --> N4
    PM --> PG
    MR --> PG
    AC --> RD
```

---

## 2. Microservice Definitions

### 2.1 Central Coordinator Services (4 Services)

| # | Service | Description | Port | Protocol |
|---|---------|-------------|------|----------|
| 1 | **Agentic Coordinator** | Meta-Agent for FL orchestration | 8001 | gRPC + Kafka |
| 2 | **Secure Aggregator** | FedAvg/FedGNN model aggregation | 8002 | gRPC + Kafka |
| 3 | **Policy Manager** | Privacy budgets + Governance | 8003 | gRPC |
| 4 | **Model Registry** | Model versions + Metrics | 8004 | gRPC |

### 2.2 Bank Node Services (6 Services)

| # | Service | Description | Port | Protocol |
|---|---------|-------------|------|----------|
| 5 | **Local Agent** | Autonomous training agent | 9001 | gRPC + Kafka |
| 6 | **Local GNN** | GNN training & inference | 9002 | gRPC |
| 7 | **Privacy Layer** | DP + Encryption | 9003 | gRPC |
| 8 | **Transaction Graph** | Graph construction + CDC | 9004 | gRPC + CDC |
| 9 | **Fraud Dashboard** | Monitoring UI | 3000 | gRPC |
| 10 | **Alerting** | Email/Ticket notifications | 9005 | Kafka |

---

## 3. Project Structure (Microservice)

```
agentic-federated-cbdc-fraud-detection/
│
├── coordinator/                          # Central Coordinator Domain
│   ├── agentic-coordinator/              # Service 1
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── secure-aggregator/                # Service 2
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── policy-manager/                   # Service 3
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── model-registry/                   # Service 4
│       ├── src/
│       ├── tests/
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── README.md
│
├── bank-node/                            # Bank Node Domain
│   ├── local-agent/                      # Service 5
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── local-gnn/                        # Service 6
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── privacy-layer/                    # Service 7
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── transaction-graph/                # Service 8
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── fraud-dashboard/                  # Service 9
│   │   ├── src/
│   │   ├── public/
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── README.md
│   └── alerting/                         # Service 10
│       ├── src/
│       ├── tests/
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── README.md
│
├── shared/                               # Shared Resources
│   ├── proto/                            # gRPC Protobuf definitions
│   ├── schemas/                          # Shared Pydantic/JSON schemas
│   └── contracts/                        # API contracts (OpenAPI)
│
├── infrastructure/                       # Infrastructure as Code
│   ├── docker-compose.yml                # Local development
│   ├── docker-compose.dev.yml            # Dev overrides
│   ├── kubernetes/                       # K8s manifests
│   └── helm/                             # Helm charts
│
├── saga/                                 # SAGA Orchestration
│   └── workflows/                        # SAGA workflow definitions
│
├── data/                                 # Data (not in services)
│   ├── raw/
│   ├── processed/
│   └── simulated/
│
├── doc/                                  # Documentation
│   ├── design/
│   ├── status/
│   └── api/
│
├── notebooks/                            # Research notebooks
└── scripts/                              # Utility scripts
```

---

## 4. Service Specifications

### 4.1 Agentic Coordinator (Meta-Agent)

```yaml
service: agentic-coordinator
domain: coordinator
port: 8001
protocols:
  - gRPC (intra-node)
  - Kafka (inter-node)
technology:
  - Python 3.11+
  - FastAPI
  - LangGraph/LangChain
responsibilities:
  - Orchestrate federated learning rounds
  - Select participating bank nodes
  - Adaptive scheduling based on node performance
  - SAGA orchestration for training workflows
communication:
  - gRPC → Secure Aggregator (Internal)
  - gRPC → Policy Manager (Internal)
  - Kafka ↔ Local Agents (External)
dependencies:
  - Redis (state management)
  - PostgreSQL (round history)
```

### 4.2 Secure Aggregator (FedAvg/FedGNN)

```yaml
service: secure-aggregator
domain: coordinator
port: 8002
protocol: gRPC + Kafka
technology:
  - Python 3.11+
  - PyTorch
  - Flower (FL framework)
responsibilities:
  - Receive encrypted model updates
  - Perform FedAvg/FedProx aggregation
  - Apply noise for differential privacy
  - Distribute global model
communication:
  - Kafka ← Bank Node Local Agents (External)
  - gRPC → Model Registry (Internal)
  - gRPC → Policy Manager (Internal)
dependencies:
  - Model Registry
  - Policy Manager
```

### 4.3 Policy Manager (Privacy + Governance)

```yaml
service: policy-manager
domain: coordinator
port: 8003
protocol: REST
technology:
  - Python 3.11+
  - FastAPI
responsibilities:
  - Manage privacy budgets (ε, δ)
  - Enforce training policies
  - Track compliance metrics
  - Governance rule enforcement
communication:
  - HTTP ← All services (policy queries)
dependencies:
  - PostgreSQL (policy storage)
```

### 4.4 Model Registry (Versions + Metrics)

```yaml
service: model-registry
domain: coordinator
port: 8004
protocol: REST
technology:
  - Python 3.11+
  - FastAPI
  - MLflow
responsibilities:
  - Store model versions
  - Track model metrics
  - Model deployment management
  - Rollback capabilities
communication:
  - HTTP ← Secure Aggregator
  - HTTP ← Local Agents (model pull)
dependencies:
  - PostgreSQL (metadata)
  - MinIO/S3 (artifact storage)
  - MLflow
```

### 4.5 Local Agent

```yaml
service: local-agent
domain: bank-node
port: 9001
protocol: gRPC + Kafka
technology:
  - Python 3.11+
  - LangGraph
responsibilities:
  - Autonomous training decisions
  - Coordinate local services
  - Submit model updates
  - Anomaly detection response
communication:
  - Kafka → Agentic Coordinator (External)
  - Kafka → Secure Aggregator (External)
  - gRPC → Local GNN, Privacy Layer (Internal)
dependencies:
  - Local GNN
  - Privacy Layer
```

### 4.6 Local GNN

```yaml
service: local-gnn
domain: bank-node
port: 9002
protocol: gRPC
technology:
  - Python 3.11+
  - PyTorch
  - PyTorch Geometric
responsibilities:
  - Local model training
  - Fraud inference
  - Feature extraction from graphs
communication:
  - gRPC ← Local Agent
  - gRPC → Transaction Graph
dependencies:
  - Transaction Graph
  - CUDA/GPU (optional)
```

### 4.7 Privacy Layer (DP + Encryption)

```yaml
service: privacy-layer
domain: bank-node
port: 9003
protocol: gRPC
technology:
  - Python 3.11+
  - Opacus
  - PySyft
  - cryptography
responsibilities:
  - Apply differential privacy to gradients
  - Encrypt model updates
  - Secure aggregation protocol
communication:
  - gRPC ← Local Agent
dependencies:
  - None (standalone)
```

### 4.8 Transaction Graph

```yaml
service: transaction-graph
domain: bank-node
port: 9004
protocols:
  - REST (queries)
  - CDC (streaming)
technology:
  - Python 3.11+
  - FastAPI
  - Neo4j driver
  - Debezium
responsibilities:
  - Build transaction graphs
  - Feature engineering
  - Real-time graph updates via CDC
communication:
  - gRPC ← Local GNN
  - CDC → Kafka (transaction events)
  - Neo4j (graph storage)
dependencies:
  - Neo4j
  - Kafka
  - Debezium
```

### 4.9 Fraud Dashboard (Monitoring UI)

```yaml
service: fraud-dashboard
domain: bank-node
port: 3000
protocol: HTTP
technology:
  - React.js / Next.js
  - TypeScript
  - WebSocket
responsibilities:
  - Real-time fraud monitoring
  - Analytics visualization
  - Alert management UI
communication:
  - HTTP → Local Agent
  - WebSocket (real-time updates)
dependencies:
  - Local Agent API
```

### 4.10 Alerting (Email/Ticket)

```yaml
service: alerting
domain: bank-node
port: 9005
protocols:
  - REST
  - Kafka Consumer
technology:
  - Python 3.11+
  - FastAPI
responsibilities:
  - Generate fraud alerts
  - Email notifications
  - Ticket creation (Jira/ServiceNow)
  - Alert lifecycle management
communication:
  - Kafka ← Transaction Graph (fraud events)
  - gRPC → Notification Providers (Internal)
dependencies:
  - Kafka
  - PostgreSQL (alert history)
  - SMTP / Notification APIs
```

---

## 5. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend Framework** | FastAPI | REST APIs |
| **RPC Framework** | gRPC | Inter-service communication |
| **ML Framework** | PyTorch + PyG | GNN training |
| **FL Framework** | Flower | Federated learning |
| **Privacy** | Opacus, PySyft | Differential privacy |
| **Agentic AI** | LangGraph | Agent orchestration |
| **Message Queue** | Apache Kafka | Event streaming |
| **CDC** | Debezium | Change data capture |
| **Graph Database** | Neo4j | Transaction graphs |
| **Relational DB** | PostgreSQL | Metadata storage |
| **Cache** | Redis | State management |
| **Object Storage** | MinIO/S3 | Model artifacts |
| **Frontend** | React.js | Dashboard UI |
| **Container** | Docker | Service packaging |
| **Orchestration** | Kubernetes | Deployment |
| **ML Ops** | MLflow | Model registry |

---

## 6. Development Phases

### Phase 1: Infrastructure Setup (Week 1-2)

| Task | Priority | Days |
|------|----------|------|
| Set up development environment | Critical | 2 |
| Create microservice folder structure | Critical | 1 |
| Implement Data Preparation pipeline (Elliptic++) | High | 2 |
| Set up shared proto/schemas | Critical | 2 |
| Docker Compose for local dev | High | 2 |
| CI/CD pipeline (GitHub Actions) | High | 2 |

### Phase 2: Core Coordinator Services (Week 3-6)

| Task | Priority | Days |
|------|----------|------|
| Policy Manager service | Critical | 5 |
| Model Registry service | Critical | 5 |
| Secure Aggregator service | Critical | 8 |
| Agentic Coordinator service | Critical | 10 |
| SAGA workflow implementation | High | 5 |

### Phase 3: Bank Node Core Services (Week 7-10)

| Task | Priority | Days |
|------|----------|------|
| Transaction Graph service | Critical | 6 |
| Local GNN service | Critical | 8 |
| Privacy Layer service | Critical | 6 |
| Local Agent service | Critical | 8 |

### Phase 4: Supporting Services (Week 11-13)

| Task | Priority | Days |
|------|----------|------|
| Alerting service | High | 4 |
| Fraud Dashboard (React) | High | 8 |
| CDC pipeline setup | High | 4 |

### Phase 5: Integration & Testing (Week 14-16)

| Task | Priority | Days |
|------|----------|------|
| Service integration tests | Critical | 5 |
| End-to-end FL workflow | Critical | 5 |
| Performance testing | High | 3 |
| Security audit | High | 3 |

### Phase 6: Deployment (Week 17-18)

| Task | Priority | Days |
|------|----------|------|
| Kubernetes manifests | High | 4 |
| Helm charts | Medium | 3 |
| Documentation | Medium | 3 |

---

## 7. SAGA Workflow Example

### Federated Learning Round SAGA

```mermaid
sequenceDiagram
    participant AC as Agentic Coordinator
    participant PM as Policy Manager
    participant SA as Secure Aggregator
    participant LA as Local Agent (Bank)
    participant MR as Model Registry
    
    Note over AC,MR: SAGA: Federated Learning Round
    
    AC->>AC: 1. Check budgets (Internal gRPC)
    AC->>AC: 2. Get global model (Internal gRPC)
    
    AC->>KF: 3. InitiateRound (Kafka Topic)
    KF-->>LA: 4. Round Notification
    LA->>LA: 5. Local Training
    LA->>KF: 6. SubmitUpdate (Kafka Topic)
    
    KF-->>SA: 7. Grad Accumuler
    SA->>SA: 8. Aggregate & DP Noise
    SA->>MR: 9. Save new model (Internal gRPC)
    SA->>KF: 10. RoundComplete (Kafka Topic)
    KF-->>AC: 11. Finished
```

---

## 8. Milestones

| Milestone | Week | Deliverables |
|-----------|------|--------------|
| **M1: Infrastructure** | 2 | Docker Compose, CI/CD, folder structure |
| **M2: Coordinator MVP** | 6 | 4 coordinator services running |
| **M3: Bank Node MVP** | 10 | 4 core bank node services |
| **M4: Full System** | 13 | All 10 services integrated |
| **M5: Production Ready** | 18 | Tested, documented, deployable |

---

## 9. Next Steps

1. [ ] Create microservice folder structure
2. [ ] Set up shared proto definitions
3. [ ] Create Docker Compose for local development
4. [ ] Begin Policy Manager service (simplest first)
5. [ ] Weekly progress reviews

---

*Last Updated: February 2026*
