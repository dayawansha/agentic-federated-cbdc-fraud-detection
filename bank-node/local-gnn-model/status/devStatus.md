# Service Development Status: Local GNN

**Current Status:** 🟢 Completed (MVP)
**Progress:** 75%
**Last Updated:** 2026-06-12

---

## Technical Specifications
- **Service Name:** local-gnn
- **Domain:** bank-node
- **Port:** 9002
- **Protocol:** REST (gRPC proto available)

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| Model Architecture (PyG) | Critical | 🟢 Completed | 100% |
| Local Training Loop | Critical | 🟢 Completed | 100% |
| Elliptic++ Processed Shard Loader | Critical | 🟢 Completed | 100% |
| Training API (`/train`) returns real weights + metrics | High | 🟢 Completed | 100% |
| Inference Engine | High | 🔴 Not Started | 0% |
| gRPC Interface | Medium | 🔵 On Hold | - |
| Unit Tests | Medium | 🔴 Not Started | 0% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- FraudGNN architecture implemented supporting GCN, GAT, and GraphSAGE.
- LocalTrainer implemented with support for weighted federated updates.
- Implemented loading for processed shards + edges + labels and produces model `state_dict` bytes for federated aggregation.
