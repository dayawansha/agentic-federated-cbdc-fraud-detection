# Service Development Status: Transaction Graph

**Current Status:** 🟡 In Progress (MVP Running)
**Progress:** 75%
**Last Updated:** 2026-06-12

---

## Technical Specifications
- **Service Name:** transaction-graph
- **Domain:** bank-node
- **Port:** 9004
- **Protocol:** REST / gRPC / CDC

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| Neo4j Data Integration | Critical | 🟢 Completed | 100% |
| REST Ingest Endpoint (`POST /transactions`) | Critical | 🟢 Completed | 100% |
| REST Account Features (`GET /accounts/{id}/features`) | High | 🟢 Completed | 100% |
| gRPC Server Skeleton | High | 🟢 Completed | 100% |
| gRPC Code Generation & Registration | High | 🟡 In Progress | 40% |
| Feature Engineering Pipeline (beyond basic stats) | Critical | 🟡 In Progress | 30% |
| CDC streaming (Kafka Producer) | High | 🟡 In Progress | 70% |
| Unit Tests (graph_service) | Medium | � In Progress | 50% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- REST endpoints implemented: `/health`, `POST /transactions`, `GET /accounts/{account_id}/features`.
- gRPC server starts, but service registration depends on generated `transaction_pb2` / `transaction_pb2_grpc` (not generated as part of the container build).
- CDC Kafka producer is implemented (`transactions.events` by default), but end-to-end validation depends on Kafka availability and topic configuration.
