import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

import notifications


class TestAlertNotifications(unittest.TestCase):
    def test_dispatch_without_channels_reports_skipped(self):
        with patch.dict(os.environ, {}, clear=True):
            result = notifications.dispatch_notifications({"alert_id": "A-1"})

        self.assertEqual(
            result,
            [
                {
                    "channel": "notifications",
                    "status": "skipped",
                    "detail": "No outbound channels configured",
                }
            ],
        )

    @patch("notifications.smtplib.SMTP")
    def test_email_notification_sends_with_starttls_and_login(self, smtp_cls):
        smtp_server = MagicMock()
        smtp_cls.return_value.__enter__.return_value = smtp_server

        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.local",
                "SMTP_PORT": "2525",
                "SMTP_USER": "fraud-bot",
                "SMTP_PASSWORD": "secret",
                "ALERT_EMAIL_TO": "ops@example.com",
                "ALERT_EMAIL_FROM": "alerts@example.com",
            },
            clear=True,
        ):
            result = notifications.send_email_notification({"alert_id": "A-2", "severity": "critical"})

        smtp_cls.assert_called_once_with("smtp.local", 2525, timeout=10)
        smtp_server.starttls.assert_called_once()
        smtp_server.login.assert_called_once_with("fraud-bot", "secret")
        smtp_server.sendmail.assert_called_once()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["channel"], "email")
        self.assertEqual(result["target"], "ops@example.com")

    @patch("notifications.requests.request")
    def test_webhook_notification_posts_ticket_payload(self, request_mock):
        response = MagicMock()
        response.status_code = 201
        request_mock.return_value = response

        alert_payload = {"alert_id": "A-3", "risk_score": 0.98}
        with patch.dict(
            os.environ,
            {
                "ALERT_TICKETING_WEBHOOK_URL": "https://tickets.local/hooks/fraud",
                "ALERT_WEBHOOK_METHOD": "post",
                "ALERT_WEBHOOK_TIMEOUT": "15",
                "ALERT_WEBHOOK_HEADERS_JSON": '{"X-Source":"fraud-dashboard"}',
                "ALERT_WEBHOOK_BEARER_TOKEN": "token-123",
            },
            clear=True,
        ):
            result = notifications.send_webhook_notification(alert_payload)

        request_mock.assert_called_once_with(
            "POST",
            "https://tickets.local/hooks/fraud",
            headers={
                "Content-Type": "application/json",
                "X-Source": "fraud-dashboard",
                "Authorization": "Bearer token-123",
            },
            json={
                "event_type": "fraud_alert",
                "alert": alert_payload,
            },
            timeout=15.0,
        )
        response.raise_for_status.assert_called_once()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["status_code"], 201)

    @patch("notifications.requests.request", side_effect=RuntimeError("webhook down"))
    def test_dispatch_records_failed_webhook_delivery(self, request_mock):
        with patch.dict(
            os.environ,
            {
                "ALERT_WEBHOOK_URL": "https://ops.local/alerts",
            },
            clear=True,
        ):
            result = notifications.dispatch_notifications({"alert_id": "A-4"})

        request_mock.assert_called_once()
        self.assertEqual(result[0]["channel"], "ticketing-webhook")
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("webhook down", result[0]["detail"])


if __name__ == "__main__":
    unittest.main()
