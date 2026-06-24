# Development Status Gap Assessment
## Agentic Federated Learning Framework for CBDC Fraud Detection

**Last Updated:** June 24, 2026  
**Document Purpose:** Service-Level Gap Assessment  
**Assessment Scope:** Requirements, design, and current microservice implementation  
**Assessment Type:** Understanding gaps between intended design and current development

---

## Executive Summary

This document explains the gap between the original project requirements/design and the current implementation at the **individual microservice level**.

The key finding is:

- the project has implemented the **intended 10 microservices**
- the system is **architecturally aligned** with the design
- several services are still implemented as **MVP-grade or prototype-grade versions**
- the main gaps are in **depth, integration, autonomy, and security maturity**, not in the absence of services

In simple terms, the system already looks like the intended architecture, but some services do not yet behave as fully as the original design expected.

---

## Project-Level View

### Overall Assessment

| Area | Status | Summary |
|------|--------|---------|
| **Service Coverage** | Strong | All major planned microservices exist |
| **Architecture Alignment** | Strong | Coordinator domain and Bank Node domain are both implemented |
| **Integration Depth** | Medium | Some services exist but are not wired together exactly as intended |
| **Agentic Behavior** | Medium-Low | Orchestration exists, but some "agentic" behavior is still workflow-driven |
| **Privacy/Security Maturity** | Medium | Privacy utilities exist, but target-state security is not fully implemented |
| **Research Evaluation Completeness** | Low-Medium | Prototype validation exists, but full experiment coverage is not yet represented in the repo |

### Main Gap Themes

| Theme | Description |
|------|-------------|
| **Autonomy Gap** | Agents exist, but several decisions are still scripted rather than fully adaptive |
| **Integration Gap** | Some services work well individually but are not connected in the exact flow described by the design |
| **Security Depth Gap** | Protected update handling exists, but not full target-state enterprise security |
| **Research Gap** | The prototype is running, but broader evaluation and experiment artifacts are still limited |

---

## Service-Level Gap Matrix

### Coordinator Domain

| Service | Expected in Design | Current Implementation | Gap Summary | Gap Severity |
|--------|---------------------|------------------------|-------------|--------------|
| **Agentic Coordinator** | Fully autonomous coordinator with durable state, intelligent participant selection, anomaly screening, and adaptive orchestration | Starts rounds, collects updates, validates metrics, negotiates weights, and triggers aggregation | More like an advanced workflow controller than a full autonomous meta-agent; state is mainly in memory and screening is heuristic | High |
| **Federated Model Aggregator** | Secure aggregation engine with broader FL strategy support | Supports protected/encrypted payload handling and `FedAvg` / `WeightedFedAvg` | Aggregation is functional, but strategy depth is narrower than the design | Medium |
| **Policy Manager** | Governance, privacy budgets, compliance rules, auditability, secure aggregation policy support | Budgets, global policies, governance rules, audit logs, and mask escrow are implemented | Strong service, but compliance is system-policy level rather than full regulatory workflow level | Low |
| **Model Registry** | Model versioning, metrics, artifact management, auditability, controlled retrieval | Stores model metadata in PostgreSQL and artifacts on disk or S3/MinIO | Core registry behavior is strong; the main gap is broader experiment and evaluation lifecycle linkage | Low |

### Bank Node Domain

| Service | Expected in Design | Current Implementation | Gap Summary | Gap Severity |
|--------|---------------------|------------------------|-------------|--------------|
| **Local Agent** | Autonomous local decision-maker for participation, training, privacy, and local constraints | Coordinates training, privacy processing, submission, and inference-based alert publication | Works as an orchestrator, but true local autonomy is still limited | High |
| **Local GNN Model** | Train on the institution's local transaction graph and graph-derived features | Trains on processed Elliptic++ CSV shards and supports inference | Model works, but it is not tightly connected to the live `transaction-graph` service | High |
| **Privacy Layer** | Differential privacy, encrypted transport, secure aggregation support, privacy evaluation | DP noise, encryption, masking, and privacy evaluation endpoints are implemented | Privacy support exists, but cryptographic maturity is below target-state design language | Medium |
| **Transaction Graph** | Local graph ingestion, storage, graph features, and CDC publication | Neo4j ingestion, features, centrality, temporal metrics, Kafka event publication | Service is good, but not used as centrally in the training pipeline as intended | Medium |
| **Alerting** | Consume transaction events, detect fraud/risk, create alerts, notify operators | Consumes `fraud.alerts`, stores recent alerts in memory, broadcasts WS events, and sends notifications | Operates more like alert distribution than full transaction-driven fraud detection | High |
| **Fraud Dashboard** | Real-time UI for monitoring, analytics, alerts, training status, and service health | Rich dashboard with analytics, service health, recent alerts, and inference watchlist | Strong implementation; main gap comes from backend simplifications rather than the dashboard itself | Low |

---

## Detailed Service Notes

### 1. Agentic Coordinator

**Expected Role**
- act as the autonomous central brain of the federated learning process
- manage round lifecycle
- choose participating agents intelligently
- enforce policy-aware coordination
- detect suspicious or malicious updates
- preserve workflow state durably across failures

**Current Role**
- starts rounds
- fetches policies
- selects agents using configured URLs and simple governance checks
- validates updates using metrics and basic consistency rules
- negotiates weights among local agents
- triggers aggregation and model registration

**Gap**
- autonomy is still limited to workflow logic and heuristics
- round state is not durably persisted as described in the design
- malicious update handling is metric-based, not a deeper poisoning-analysis approach
- runtime behavior is still close to a single-node MVP path

**Assessment**
- the service exists and is important, but it is not yet the full research-grade meta-agent originally envisioned

### 2. Federated Model Aggregator

**Expected Role**
- aggregate protected updates securely
- support multiple FL strategies
- adapt aggregation choices to data quality and node behavior

**Current Role**
- loads protected/encrypted model payloads
- resolves encrypted submissions
- performs `FedAvg` or `WeightedFedAvg`
- computes weighted global metrics

**Gap**
- only a small subset of possible strategies is implemented
- aggregation behavior is still practical and MVP-oriented rather than broad and experimental

**Assessment**
- solid prototype aggregator, but narrower than the full design ambition

### 3. Policy Manager

**Expected Role**
- manage privacy budgets
- maintain governance rules
- control eligibility and compliance constraints
- support secure aggregation governance and auditability

**Current Role**
- persists privacy budgets
- stores versioned global policies
- tracks governance agents
- records audit events
- stores secure aggregation mask shares

**Gap**
- strongest alignment among services
- remaining gap is mostly in enterprise/regulatory depth, not core functionality

**Assessment**
- one of the most complete services relative to the original design

### 4. Model Registry

**Expected Role**
- manage global model versions
- store artifacts and metrics
- provide retrieval for downstream training rounds
- support auditability and experiment traceability

**Current Role**
- registers model versions
- persists metadata in PostgreSQL
- stores artifacts on local disk or S3/MinIO
- supports latest-model retrieval and version listing

**Gap**
- very close to intended prototype behavior
- broader research experiment tracking is still limited

**Assessment**
- mature enough for prototype use, with only a modest gap relative to the design

### 5. Local Agent

**Expected Role**
- decide whether to join a round
- check local readiness and local constraints
- orchestrate training and privacy steps
- manage outbound participation safely and autonomously

**Current Role**
- pulls the global model
- triggers local GNN training
- calls privacy-layer services
- submits updates to the coordinator
- publishes inference-driven alerts

**Gap**
- local readiness and participation are not deeply evaluated
- "agentic" behavior is mostly workflow execution
- local autonomy is present in structure more than in actual decision depth

**Assessment**
- functionally useful, but still closer to a scripted orchestration service than a reasoning agent

### 6. Local GNN Model

**Expected Role**
- train fraud models directly on the institution's local transaction graph
- use graph-derived features from the live graph system
- provide graph-native fraud inference

**Current Role**
- loads processed CSV shard files
- builds graph tensors from preprocessed data
- trains a hybrid GNN
- exposes training and inference endpoints

**Gap**
- strongest mismatch in the Bank Node domain
- model training uses static prepared datasets, not the live `transaction-graph` microservice
- the intended graph-service-to-GNN integration is not fully realized

**Assessment**
- the model itself is good, but the implementation path is simpler than the architecture promised

### 7. Privacy Layer

**Expected Role**
- apply differential privacy
- protect transport
- support secure aggregation
- enable privacy analysis and leakage evaluation

**Current Role**
- applies DP noise
- encrypts and decrypts payloads
- prepares masked secure aggregation updates
- exposes privacy evaluation and gradient clipping endpoints

**Gap**
- privacy support is real and useful
- however, the privacy/security design is still prototype-grade rather than full target-state enterprise-grade
- secure aggregation support is simpler than the stronger protocol described in the design

**Assessment**
- a strong prototype privacy utility service with moderate maturity gap

### 8. Transaction Graph

**Expected Role**
- receive and store local transaction data
- represent it in Neo4j
- expose graph features for analytics and learning
- publish CDC-style events to Kafka

**Current Role**
- stores account and transaction graph data
- exposes account features, centrality, and temporal metrics
- publishes transaction events to Kafka

**Gap**
- service functionality itself is good
- main issue is that the ML side does not depend on it as directly as intended
- it is underused in the actual model-training flow

**Assessment**
- one of the stronger bank-side services, but not as central to the learning pipeline as the design planned

### 9. Alerting

**Expected Role**
- consume transaction events
- run detection or rule checks
- create fraud alerts
- notify operators and downstream systems

**Current Role**
- consumes `fraud.alerts`
- stores recent alerts in memory
- pushes WebSocket updates
- sends notifications via email and webhook

**Gap**
- biggest role mismatch in the bank-side support services
- it behaves more as an alert receiver/distributor than the main detector of suspicious transaction events
- alert history is not persisted in a relational store despite that being implied in the design notes

**Assessment**
- operationally useful, but narrower than the original intended responsibility

### 10. Fraud Dashboard

**Expected Role**
- provide a real-time monitoring and analytics UI
- show service health
- show alerts and fraud trends
- support operational visibility for the bank node

**Current Role**
- exposes service health views
- shows recent alerts and analytics
- displays inference watchlists and transaction activity
- uses polling and WebSocket updates

**Gap**
- smallest service-level gap
- the dashboard is relatively strong
- most limitations come from backend simplifications rather than the dashboard itself

**Assessment**
- the dashboard is ahead of several backend services in maturity

---

## Strongest and Weakest Alignment

### Strongest Alignment to Design

| Service | Reason |
|--------|--------|
| **Policy Manager** | Governance, policies, budgets, and audit trails are strongly represented |
| **Model Registry** | Core artifact and metadata lifecycle is implemented well |
| **Transaction Graph** | Graph service functionality is good and technically meaningful |
| **Fraud Dashboard** | Rich operator-facing functionality is already present |

### Largest Gaps to Design

| Service | Reason |
|--------|--------|
| **Agentic Coordinator** | Still more workflow-driven than fully autonomous and durable |
| **Local Agent** | Limited true local decision-making |
| **Local GNN Model** | Not tightly integrated with the live graph-service architecture |
| **Alerting** | Role shifted from fraud detection to alert distribution/notification |

---

## Cross-Service Interpretation

### What the project has achieved

- the intended microservice architecture exists
- coordinator and bank domains are clearly separated
- the prototype supports end-to-end federated learning rounds
- privacy-preserving update handling is implemented
- model lifecycle, governance, alerts, and dashboard visibility are all present

### What remains different from the original design

- agentic behavior is lighter than initially described
- some service interactions are simplified
- graph learning is not fully live-service driven
- alerting is not the primary fraud detector from transaction CDC flow
- security and secure aggregation are not at full target-state maturity
- research evaluation artifacts are still less complete than the design ambitions

---

## Final Conclusion

This project does **not** mainly suffer from missing services.

Instead, the current gap is that several microservices are implemented as **working prototype versions** of what the design described as a more:

- autonomous
- tightly integrated
- secure
- and research-complete system

So the best summary is:

**The development is architecturally correct, but behaviorally simplified.**

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-24 | Created `devStatus-0.2.md` with service-level gap assessment between design/requirements and current implementation | GPT-5.4 |

---

*Last Updated: June 24, 2026*
