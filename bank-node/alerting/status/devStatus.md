# Development Status: Alerting

**Current Status:** 🟢 Complete
**Progress:** 100%
**Last Updated:** 2026-06-24

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
| Expanded Test Suite (API + channel config + ring buffer) | Medium | 🟢 Completed | 100% |
| FastAPI Lifespan Migration (deprecation fix) | Low | 🟢 Completed | 100% |

---

## Latest Verified Development

- `alerting` pod running in Kubernetes; `GET /health` responds on port `9005`.
- Kafka consumer processes messages from `fraud.alerts` topic, dispatches to configured outbound channels, stores in the in-memory ring buffer, and pushes to WebSocket clients.
- `GET /alerts/recent` returns latest alerts (newest-first) with per-channel `notification_results` included.
- `GET /alerts/channels` reports which outbound channels (email / ticketing-webhook) are active and their configuration.
- WebSocket endpoint `/ws/alerts` fans out every incoming alert to all connected dashboard clients in real time.
- **Deprecated `@app.on_event("startup")` migrated to modern FastAPI `lifespan` context manager** — eliminates DeprecationWarning in logs and test output.
- **Full test suite: 28/28 passing** across:
  - `TestDispatchNotifications` — no-channels skipped, both-channels dispatched, failed channel recorded.
  - `TestGetNotificationChannels` — shape, email/webhook configured/unconfigured, legacy-URL fallback.
  - `TestSendEmailNotification` — skipped, STARTTLS+login, no-STARTTLS, no-login, SMTP failure.
  - `TestSendWebhookNotification` — skipped, correct payload+headers, default method, network failure, HTTP error.
  - `TestStoreRecentAlert` — store, dedup on alert_id, ring-buffer eviction, no-id append.
  - `TestAlertingAPIEndpoints` — `/health`, `/alerts/recent` (empty, populated, limit), `/alerts/channels` (count, configured count).

---

## Implementation Notes
- **Ring buffer**: `recent_alerts` is capped at `RECENT_ALERTS_MAX` (default 200). Alerts with the same `alert_id` are replaced rather than duplicated before appending.
- **No SMTP/webhook in dev**: Both outbound channels return `skipped` when unconfigured — the service starts cleanly without env vars.
- **Lifespan pattern**: `_broadcast_worker` coroutine and the Kafka consumer daemon thread are both started in the `lifespan` context manager on startup.
