# Service Development Status: Local GNN

**Current Status:** 🟡 In Progress
**Progress:** 40%

---

## Technical Specifications
- **Service Name:** local-gnn
- **Domain:** bank-node
- **Port:** 9002
- **Protocol:** gRPC

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| Model Architecture (PyG) | Critical | 🟢 Completed | 100% |
| Local Training Loop | Critical | 🟡 In Progress | 60% |
| Inference Engine | High | 🔴 Not Started | 0% |
| gRPC Interface | High | 🟡 In Progress | 20% |
| Unit Tests | Medium | 🔴 Not Started | 0% |
| Dockerization | Medium | 🔴 Not Started | 0% |

---

## Notes & Blockers
- FraudGNN architecture implemented supporting GCN, GAT, and GraphSAGE.
- LocalTrainer implemented with support for weighted federated updates.
- Need to implement data loaders for the processed Elliptic++ shards.complete.
