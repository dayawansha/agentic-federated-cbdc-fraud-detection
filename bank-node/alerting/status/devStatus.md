# Development Status: Alerting

**Current Status:** 🟢 Feature Complete (Local Runtime Blocked by Host Disk Pressure)
**Progress:** 92%
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
| Notification Logic (Email) | Medium | 🟢 Completed | 100% |
| Ticketing Webhook Integration | Low | 🟢 Completed | 100% |
| Notification Channel API (`/alerts/channels`) | Medium | 🟢 Completed | 100% |
| Unit Tests | Medium | 🟢 Completed | 100% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- Kafka consumer stores recent alerts in-memory and broadcasts events via WebSocket.
- Outbound channels now include SMTP email plus a generic ticketing webhook using `ALERT_TICKETING_WEBHOOK_URL` or `ALERT_WEBHOOK_URL`.
- Recent alerts now persist per-channel `notification_results`, and `/alerts/channels` exposes which outbound channels are configured.
- The service is running in the validated `minikube` deployment and backs the live dashboard feed via `/alerts/recent` and `/ws/alerts`; a fresh-tag redeploy is currently blocked by host disk pressure rather than service code.
