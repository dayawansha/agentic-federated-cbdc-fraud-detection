# Alerting Service

Kafka consumer for real-time fraud events, WebSocket event broadcaster, SMTP email notifier, and ticketing webhook dispatcher.

## Port
- **`9005`** (REST API & WebSockets)

## Service Responsibilities
The `alerting` service consumes fraud alerts published by the system's inference engines, processes them, and broadcasts them to operational queues and dashboards.

- **Kafka Consumer Loop**: Listens continuously to the `fraud.alerts` topic, deserializing transaction details, confidence scores, and origin bank nodes.
- **Real-Time Streaming**: Implements WebSocket endpoints to push live fraud notifications directly to frontend monitors (`fraud-dashboard`).
- **SMTP Email Notifications**: Dispatches formatted HTML/Plaintext warning emails to security teams when SMTP parameters are configured.
- **Ticketing & Webhook Dispatch**: Translates alert events into HTTP payloads and fires them at target external endpoints (e.g. Jira, Slack, PagerDuty, or custom bank ops tools) with customizable authorization headers.
- **Alert Buffering**: Holds an in-memory ring buffer of the most recent fraud alerts for quick search retrieval.

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
