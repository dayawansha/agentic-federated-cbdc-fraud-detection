# Development Status: Local GNN

**Current Status:** 🟢 Completed (Training + Inference Runtime Validated)
**Progress:** 100%
**Last Updated:** 2026-06-24

---

## Technical Specifications
- **Service Name:** local-gnn
- **Domain:** bank-node
- **Port:** 9002
- **Protocol:** REST

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| Model Architecture (PyG) | Critical | 🟢 Completed | 100% |
| Local Training Loop | Critical | 🟢 Completed | 100% |
| Elliptic++ Processed Shard Loader | Critical | 🟢 Completed | 100% |
| Training API (`/train`) returns real weights + metrics | High | 🟢 Completed | 100% |
| Inference Engine (`/infer`) | High | 🟢 Completed | 100% |
| REST Training Interface | Medium | 🟢 Completed | 100% |
| Unit Tests | Medium | 🟢 Completed | 100% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- FraudGNN architecture implemented supporting GCN, GAT, and GraphSAGE.
- LocalTrainer implemented with support for weighted federated updates.
- Implemented loading for processed shards + edges + labels and produces model `state_dict` bytes for federated aggregation.
- Implemented a runtime dataset-path fix so the service resolves training files correctly in both the repository and container image layouts.
- Updated the Docker image to bundle the required processed shard, edges, and class-label CSV files for Kubernetes runtime.
- The service is validated in the current `minikube` deployment and its `/health` endpoint responds successfully on port `9002`.
- Added a real `/infer` endpoint that returns ranked fraud predictions for the loaded shard or a selected set of `tx_id` values.
- Added root-runnable local tests covering `/train` request handling, ranked `/infer` selection, and missing `tx_id` error handling.
- Remaining gaps are now outside the MVP path: deeper model benchmarking and downstream adoption of inference results.
