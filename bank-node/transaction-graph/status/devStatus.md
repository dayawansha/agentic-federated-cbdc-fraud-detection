# Development Status: Transaction Graph

**Current Status:** 🟡 In Progress (MVP Running and Dataset-Validated)
**Progress:** 85%
**Last Updated:** 2026-06-13

---

## Technical Specifications
- **Service Name:** transaction-graph
- **Domain:** bank-node
- **Port:** 9004
- **Protocol:** REST / CDC

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| Neo4j Data Integration | Critical | 🟢 Completed | 100% |
| REST Ingest Endpoint (`POST /transactions`) | Critical | 🟢 Completed | 100% |
| REST Account Features (`GET /accounts/{id}/features`) | High | 🟢 Completed | 100% |
| REST Query and Ingest APIs | High | 🟢 Completed | 100% |
| Feature Engineering Pipeline (beyond basic stats) | Critical | 🟡 In Progress | 30% |
| CDC Streaming (Kafka Producer) | High | 🟢 Completed | 100% |
| Processed Dataset Bootstrap / Import Support | High | 🟢 Completed | 100% |
| Kubernetes Runtime Validation | High | 🟢 Completed | 100% |
| End-to-End Validation (API -> Neo4j -> Features -> Kafka) | Critical | 🟢 Completed | 100% |
| Unit Tests (graph_service) | Medium | 🟡 In Progress | 50% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Latest Verified Development
- `transaction-graph` pod is running in Kubernetes and `GET /health` responds successfully on port `9004`.
- Live inserts were verified through `POST /transactions`; Neo4j now contains `Account` and `Transaction` nodes created by the service.
- `GET /accounts/{account_id}/features` returns expected aggregates from Neo4j for inserted accounts.
- Kafka CDC is working end-to-end; inserted transactions are published to topic `transactions.events`.
- Reusable bootstrap script added at `scripts/load_transaction_graph_processed.py` to load a controlled subset from `train-data/processed/txs_edges_processed.csv` and `txs_nodes_processed.csv` through the service API.

---

## Notes & Remaining Gaps
- REST endpoints implemented and validated: `/health`, `POST /transactions`, `GET /accounts`, `GET /accounts/{account_id}/features`.
- The bootstrap script maps processed Elliptic++ edge rows into service payloads and derives a positive display amount from processed node features for graph visualization and API validation.
- Legacy RPC scaffolding has been removed; synchronous access is now standardized on REST only.
- Advanced feature engineering is still limited to basic account statistics; graph-centrality, temporal windows, and richer neighbor aggregations remain future work.
- Unit test coverage exists around graph service logic, but runtime/API/bootstrap integration tests are still missing.
