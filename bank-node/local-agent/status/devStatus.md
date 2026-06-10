# Service Development Status: Local Agent

**Current Status:** 🟡 In Progress
**Progress:** 20%

---

## Technical Specifications
- **Service Name:** local-agent
- **Domain:** bank-node
- **Port:** 9001
- **Protocol:** gRPC / REST

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| API Definitions (Proto) | High | 🟢 Completed | 100% |
| LangGraph Workflow | Critical | 🟡 In Progress | 40% |
| Training Pipeline Integration| Critical | 🔴 Not Started | 0% |
| Coordinator Client (gRPC) | High | 🔴 Not Started | 0% |
| Unit Tests | Medium | 🔴 Not Started | 0% |
| Dockerization | Medium | 🔴 Not Started | 0% |

---

## Notes & Blockers
- Initial LangGraph workflow for local training orchestration implemented.
- Need to integrate with Local GNN, Privacy Layer, and Transaction Graph services.
