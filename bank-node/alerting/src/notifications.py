import json
import os
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List

import requests


def _result(channel: str, status: str, detail: str, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "channel": channel,
        "status": status,
        "detail": detail,
    }
    payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def get_notification_channels() -> List[Dict[str, Any]]:
    email_target = os.getenv("ALERT_EMAIL_TO")
    email_host = os.getenv("SMTP_HOST")
    webhook_url = os.getenv("ALERT_TICKETING_WEBHOOK_URL") or os.getenv("ALERT_WEBHOOK_URL")

    return [
        {
            "channel": "email",
            "configured": bool(email_host and email_target),
            "target": email_target if email_target else None,
        },
        {
            "channel": "ticketing-webhook",
            "configured": bool(webhook_url),
            "target": webhook_url,
            "method": os.getenv("ALERT_WEBHOOK_METHOD", "POST").upper(),
        },
    ]


def _build_email_message(payload: Dict[str, Any]) -> MIMEText:
    subject = f"Fraud Alert: {payload.get('alert_id', 'unknown')}"
    body = json.dumps(payload, indent=2, sort_keys=True)

    msg = MIMEText(body)
    msg["Subject"] = subject
    return msg


def send_email_notification(payload: Dict[str, Any]) -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST")
    to_addr = os.getenv("ALERT_EMAIL_TO")
    if not host or not to_addr:
        return _result("email", "skipped", "SMTP host or recipient is not configured")

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("ALERT_EMAIL_FROM") or user or "alerts@local"
    use_starttls = _env_bool("SMTP_STARTTLS", True)

    msg = _build_email_message(payload)
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_starttls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    except Exception as exc:
        return _result("email", "failed", str(exc), target=to_addr)

    return _result("email", "sent", "Email notification delivered", target=to_addr)


def _build_webhook_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    headers_json = os.getenv("ALERT_WEBHOOK_HEADERS_JSON")
    if headers_json:
        parsed = json.loads(headers_json)
        if not isinstance(parsed, dict):
            raise ValueError("ALERT_WEBHOOK_HEADERS_JSON must decode to a JSON object")
        headers.update({str(key): str(value) for key, value in parsed.items()})

    bearer_token = os.getenv("ALERT_WEBHOOK_BEARER_TOKEN")
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    return headers


def send_webhook_notification(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = os.getenv("ALERT_TICKETING_WEBHOOK_URL") or os.getenv("ALERT_WEBHOOK_URL")
    if not url:
        return _result("ticketing-webhook", "skipped", "Webhook URL is not configured")

    method = os.getenv("ALERT_WEBHOOK_METHOD", "POST").upper()
    timeout = float(os.getenv("ALERT_WEBHOOK_TIMEOUT", "10"))

    try:
        response = requests.request(
            method,
            url,
            headers=_build_webhook_headers(),
            json={
                "event_type": "fraud_alert",
                "alert": payload,
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as exc:
        return _result("ticketing-webhook", "failed", str(exc), target=url, method=method)

    return _result(
        "ticketing-webhook",
        "sent",
        "Webhook notification delivered",
        target=url,
        method=method,
        status_code=response.status_code,
    )


def dispatch_notifications(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    channels = get_notification_channels()
    configured_channels = [channel["channel"] for channel in channels if channel.get("configured")]
    if not configured_channels:
        return [_result("notifications", "skipped", "No outbound channels configured")]

    results: List[Dict[str, Any]] = []

    if "email" in configured_channels:
        results.append(send_email_notification(payload))
    if "ticketing-webhook" in configured_channels:
        results.append(send_webhook_notification(payload))

    return results
