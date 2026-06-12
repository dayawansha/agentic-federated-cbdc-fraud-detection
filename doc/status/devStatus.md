# Development Status
## Agentic Federated Learning Framework for CBDC Fraud Detection

**Last Updated:** June 12, 2026  
**Current Phase:** MVP Complete (End-to-End Round Flow Running)  
**Overall Progress:** 85%

---

## Executive Summary

### Project Overview

| Metric | Value |
|--------|-------|
| **Project Start Date** | February 2026 |
| **Target Completion** | September 2026 |
| **Total Services** | 10 microservices |
| **Architecture** | Microservice (Domain-Driven) |
| **Communication** | Intra: gRPC, Inter: Kafka/CDC |

### Project Achievements

- **End-to-End FL Round (MVP)**: Implemented a working round flow across Coordinator → Agents → Aggregator → Registry → Policy Manager.
- **Local GNN Training (Real Data)**: Local GNN trains on processed Elliptic++ shard and returns real model weights and metrics.
- **Privacy Layer**: Differential privacy noise application and encryption utilities exposed via REST.
- **Operational Visibility (MVP)**: Alerting supports recent alerts API and WebSocket broadcast; Dashboard consumes agent status + alerts.

### Key Milestones

| Milestone | Target | Status |
|-----------|--------|--------|
| M1: Infrastructure | Week 2 | 🟢 Completed |
| M2: Coordinator MVP | Week 6 | 🟢 Completed |
| M3: Bank Node MVP | Week 10 | 🟢 Completed |
| M4: Full System (MVP Flow) | Week 13 | 🟢 Completed |
| M5: Production Ready | Week 18 | 🟡 In Progress |

### Overall Metrics

```
Services Running:       10 / 10
MVP Round Flow:         1 / 1
Persistence (DB):       2 / 2 (Policy + Registry)
Unit Tests:             1 / 10 (partial)
```

### Recent Decisions

- **Jun 12, 2026:** Standardized model-weight payload transport via base64 JSON between services.
- **Jun 12, 2026:** Implemented REST-based Secure Aggregator `/aggregate` for FedAvg interoperability.
- **Jun 12, 2026:** Migrated Policy Manager and Model Registry from in-memory storage to PostgreSQL.

---

## Service Development Status

### Coordinator Domain

| Service | Status | Progress | Notes |
|---------|--------|----------|-------|
| Agentic Coordinator | 🟢 MVP Complete | 85% | Orchestrates round and integrates with aggregator/registry/policy |
| Secure Aggregator | 🟢 MVP Complete | 80% | FedAvg via REST `/aggregate` (+ optional DP noise) |
| Policy Manager | 🟢 MVP Complete | 80% | Budgets persisted in PostgreSQL |
| Model Registry | 🟢 MVP Complete | 75% | Versions persisted in PostgreSQL; artifacts stored on disk |

### Bank Node Domain

| Service | Status | Progress | Notes |
|---------|--------|----------|-------|
| Local Agent | 🟢 MVP Complete | 80% | Trains + applies privacy + submits update to coordinator |
| Local GNN | 🟢 MVP Complete | 75% | Trains on processed Elliptic++ shard; returns weights + metrics |
| Privacy Layer | 🟢 MVP Complete | 80% | DP + encrypt/decrypt REST endpoints |
| Transaction Graph | 🟡 In Progress | 70% | Neo4j + CDC producer; basic feature endpoint added |
| Fraud Dashboard | 🟡 In Progress | 60% | Polls agent status + shows alerts; WS updates from alerting |
| Alerting | 🟡 In Progress | 75% | Recent alerts + WS broadcast; optional SMTP |

---

## Infrastructure Status

| Component | Status | Notes |
|-----------|--------|-------|
| Folder Structure | 🟢 Completed | Full microservice structure initialized |
| Shared Proto/Schemas | 🟢 Completed | gRPC protos and Pydantic schemas ready |
| Docker Compose | 🟢 Completed | Local multi-service environment ready |
| CI/CD Pipeline | 🔴 Not Started | - |
| Kubernetes Manifests | 🟡 In Progress | Helm chart present; service-level maturity still evolving |

---

## Phase Progress

### Phase 1: Infrastructure Setup (Week 1-2)
- [x] Set up development environment
- [x] Create microservice folder structure
- [x] Implement Data Preparation pipeline (Elliptic++)
- [x] Set up shared proto/schemas
- [x] Docker Compose for local dev
- [ ] CI/CD pipeline (GitHub Actions)

### Phase 2: Core Coordinator Services (Week 3-6)
- [x] Policy Manager service (REST + PostgreSQL budgets)
- [x] Model Registry service (REST + PostgreSQL versions)
- [x] Secure Aggregator service (FedAvg via REST)
- [x] Agentic Coordinator service (LangGraph-based orchestration + integrations)
- [x] Round workflow (MVP)

### Phase 3: Bank Node Core Services (Week 7-10)
- [🟡] Transaction Graph service (Neo4j + Kafka)
- [x] Local GNN service (training on processed shard + weights output)
- [x] Privacy Layer service (DP + encrypt/decrypt)
- [x] Local Agent service (training + privacy + coordinator submission)

### Phase 4: Supporting Services (Week 11-13)
- [🟡] Alerting service (Kafka + WS + recent alerts)
- [🟡] Fraud Dashboard (polling + WS)
- [ ] CDC pipeline setup

### Phase 5: Integration & Testing (Week 14-16)
- [x] Service integration (Internal Bank Node)
- [x] Service integration (Coordinator to Agent)
- [🟡] End-to-end FL workflow test script
- [🟡] Performance benchmarking suite
- [🟡] Privacy & Security Audit suite

### Phase 6: Deployment (Week 17-18)
- [x] Kubernetes manifests
- [x] Helm charts for 10 microservices
- [x] Cloud persistent storage (PVC)
- [x] Prometheus/Grafana Monitoring stack
- [x] Final handover documentation

---

## Status Legend

| Icon | Meaning |
|------|---------|
| 🔴 | Not Started |
| 🟡 | In Progress |
| 🟢 | Completed |
| 🔵 | On Hold |
| ⚪ | Blocked |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-02-09 | Initial status document created | - |
| 2026-02-09 | Updated devPlan.md with microservice architecture | - |
| 2026-06-12 | Updated status to reflect MVP end-to-end round flow + DB persistence | - |

---

*Last Updated: June 12, 2026*
