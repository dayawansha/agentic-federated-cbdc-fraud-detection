# Development Status: Alerting

**Current Status:** 🟡 In Progress (MVP Runtime Validated)
**Progress:** 75%
**Last Updated:** 2026-06-15

---

## Technical Specifications
- **Service Name:** alerting
- **Domain:** bank-node
- **Port:** 9005
- **Protocol:** REST / Kafka Consumer / WebSocket

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| API Definitions | High | 🟢 Completed | 100% |
| Kafka Consumer Setup | High | 🟢 Completed | 100% |
| Recent Alerts API (`/alerts/recent`) | High | 🟢 Completed | 100% |
| Real-time Alerts (WebSocket) | High | 🟢 Completed | 100% |
| Notification Logic (Email) | Medium | 🟡 In Progress | 50% |
| Ticketing Integration | Low | 🔴 Not Started | 0% |
| Unit Tests | Medium | 🔴 Not Started | 0% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- Kafka consumer stores recent alerts in-memory and broadcasts events via WebSocket.
- SMTP support is optional and controlled by environment variables; SMS/ticketing are not implemented.
- The service is running in the validated `minikube` deployment and backs the live dashboard feed via `/alerts/recent` and `/ws/alerts`.
