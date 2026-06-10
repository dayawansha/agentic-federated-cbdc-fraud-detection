# Service Development Status: Alerting

**Current Status:** 🟡 In Progress
**Progress:** 20%

---

## Technical Specifications
- **Service Name:** alerting
- **Domain:** bank-node
- **Port:** 9005
- **Protocol:** REST / Kafka Consumer

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| API Definitions | High | 🟢 Completed | 100% |
| Kafka Consumer Setup | High | 🟡 In Progress | 50% |
| Notification Logic (Email/SMS) | Medium | 🔴 Not Started | 0% |
| Ticketing Integration | Low | 🔴 Not Started | 0% |
| Unit Tests | Medium | 🔴 Not Started | 0% |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- Initial Kafka consumer skeleton implemented to listen for fraud alerts.
- Need to integrate with actual notification providers (SMTP/Twilio).
