# Alerting

Kafka-backed fraud alert delivery with recent-alert API, WebSocket broadcast, and outbound notification channels.

## Runtime Name
- `alerting`

## Responsibilities
- Generate fraud alerts
- Expose recent alerts
- Broadcast real-time alerts over WebSocket
- Deliver email notifications when SMTP is configured
- Forward fraud alerts to ticketing or ops tools through a generic webhook
- Report configured outbound channels through `GET /alerts/channels`

## Technology Stack
- Python 3.11+
- FastAPI
- Kafka
- WebSocket
- Requests

## Port
- 9005

## Notification Configuration
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS`
- `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`
- `ALERT_TICKETING_WEBHOOK_URL` or `ALERT_WEBHOOK_URL`
- `ALERT_WEBHOOK_METHOD`, `ALERT_WEBHOOK_TIMEOUT`
- `ALERT_WEBHOOK_HEADERS_JSON`, `ALERT_WEBHOOK_BEARER_TOKEN`
