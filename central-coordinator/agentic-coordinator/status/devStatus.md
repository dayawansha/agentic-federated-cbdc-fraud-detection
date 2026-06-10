# Service Development Status: Agentic Coordinator

**Current Status:** 🟡 In Progress
**Progress:** 25%

---

## Technical Specifications
- **Service Name:** agentic-coordinator
- **Domain:** coordinator
- **Port:** 8001
- **Protocol:** gRPC / REST

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| API Definitions (Proto) | High | 🟢 Completed | 100% |
| Business Logic (SAGA) | Critical | 🟡 In Progress | 20% |
| LangGraph Integration| Critical | 🟡 In Progress | 30% |
| Unit Tests | Medium | 🔴 Not Started | 0% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- Initial LangGraph workflow for orchestrating federated rounds implemented.
- Need to integrate with Secure Aggregator and Policy Manager via gRPC/REST.
