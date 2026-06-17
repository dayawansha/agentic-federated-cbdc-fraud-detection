# Alerting Service

Kafka consumer for real-time fraud events, WebSocket event broadcaster, SMTP email notifier, and ticketing webhook dispatcher.

## Port
- **`9005`** (REST API & WebSockets)

## Service Responsibilities
The `alerting` service is the **alarm system (communicator)** of the bank node. It listens for fraud signals from the GNN AI engine and distributes warnings to the security team and dashboards.

1. **Listening for Alarms (Kafka Consumer Loop)**
   - **What it does:** Monitors the system's message queue for any new fraud predictions.
   - **How it works:** It listens to the `fraud.alerts` Kafka stream, instantly catching transaction details, security confidence scores, and origin bank details.

2. **Broadcasting Live Updates (Real-Time Streaming)**
   - **What it does:** Pushes live alerts to operator dashboards so they pop up immediately on screen.
   - **How it works:** It uses WebSockets to establish a continuous connection, pushing alerts to the `fraud-dashboard` without the UI needing to refresh.

3. **Sending Warning Emails (SMTP Email Notifications)**
   - **What it does:** Alerts the security operations team via email when critical fraud is detected.
   - **How it works:** It formats a message detailing the suspicious transaction and emails it to security administrators using standard SMTP protocols.

4. **Triggering External Systems (Ticketing & Webhook Dispatch)**
   - **What it does:** Reports fraud events to external bank systems (like Slack channels, Jira boards, or PagerDuty schedules).
   - **How it works:** It sends secure HTTP webhooks containing transaction summaries to designated third-party API addresses.

5. **Storing Recent History (Alert Buffering)**
   - **What it does:** Keeps a list of the latest alerts handy for quick review.
   - **How it works:** It maintains a short in-memory buffer of recent alerts so operators can quickly search or filter them.

---

## API & WebSocket Endpoints

### 1. General & Query
- `GET /health`: Returns basic health status.
- `GET /alerts/recent?limit={limit}`: Fetches recently processed fraud alert objects.
- `GET /alerts/channels`: Details which notification channels (Email, Webhooks) are currently active based on env variables.

### 2. Streaming Connection
- `WS /ws/alerts`: WebSocket server endpoint. Clients (like UI dashboards) connect here to receive live JSON alert events.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker host | `"localhost:9092"` |
| `KAFKA_ALERT_TOPIC` | Topic name for alerts | `"fraud.alerts"` |
| `SMTP_HOST` / `SMTP_PORT` | Outgoing email server parameters | None |
| `SMTP_USER` / `SMTP_PASSWORD`| Mail account credentials | None |
| `ALERT_EMAIL_TO` / `FROM` | Destination and sender email addresses | None |
| `ALERT_WEBHOOK_URL` | Destination address for ticket forwarding | None |
| `ALERT_WEBHOOK_METHOD` | Webhook HTTP verb (`POST`, `PUT`) | `"POST"` |
| `ALERT_WEBHOOK_HEADERS_JSON`| JSON string containing headers | None |
| `ALERT_WEBHOOK_BEARER_TOKEN`| HTTP Header Authorization bearer token | None |

---

## Technology Stack
- **Streaming Ingestion**: `confluent-kafka` (Fast C-based Kafka client bindings)
- **Framework**: FastAPI, Uvicorn, Pydantic, WebSockets
- **Communications**: `requests` (Webhook dispatch), Python `smtplib` (Email client)
