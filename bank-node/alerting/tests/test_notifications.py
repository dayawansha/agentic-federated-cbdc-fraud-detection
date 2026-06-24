"""
Expanded test suite for the alerting service.

Coverage:
  - notifications.py — all paths (dispatch, email, webhook, channels)
  - main.py          — API routes via FastAPI TestClient
  - _store_recent_alert — deduplication and ring-buffer eviction
"""
import os
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Bootstrap: add src/ to path so imports work without installing the package
# ---------------------------------------------------------------------------
SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

import notifications  # noqa: E402


# ===========================================================================
# notifications.py — dispatch_notifications
# ===========================================================================

class TestDispatchNotifications(unittest.TestCase):
    def test_no_channels_configured_returns_skipped(self):
        with patch.dict(os.environ, {}, clear=True):
            result = notifications.dispatch_notifications({"alert_id": "A-1"})

        self.assertEqual(result, [{
            "channel": "notifications",
            "status": "skipped",
            "detail": "No outbound channels configured",
        }])

    @patch("notifications.send_email_notification")
    @patch("notifications.send_webhook_notification")
    def test_both_channels_are_dispatched(self, mock_wh, mock_em):
        mock_em.return_value = {"channel": "email", "status": "sent", "detail": "ok"}
        mock_wh.return_value = {"channel": "ticketing-webhook", "status": "sent", "detail": "ok"}

        payload = {"alert_id": "A-5"}
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.local",
            "ALERT_EMAIL_TO": "ops@example.com",
            "ALERT_TICKETING_WEBHOOK_URL": "https://hooks.local/fraud",
        }, clear=True):
            result = notifications.dispatch_notifications(payload)

        mock_em.assert_called_once_with(payload)
        mock_wh.assert_called_once_with(payload)
        self.assertEqual(len(result), 2)

    @patch("notifications.requests.request", side_effect=RuntimeError("webhook down"))
    def test_failed_webhook_is_recorded(self, _mock):
        with patch.dict(os.environ, {
            "ALERT_WEBHOOK_URL": "https://ops.local/alerts",
        }, clear=True):
            result = notifications.dispatch_notifications({"alert_id": "A-4"})

        self.assertEqual(result[0]["channel"], "ticketing-webhook")
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("webhook down", result[0]["detail"])


# ===========================================================================
# notifications.py — get_notification_channels
# ===========================================================================

class TestGetNotificationChannels(unittest.TestCase):
    def test_returns_two_channel_entries(self):
        with patch.dict(os.environ, {}, clear=True):
            channels = notifications.get_notification_channels()
        self.assertEqual(len(channels), 2)
        names = {c["channel"] for c in channels}
        self.assertIn("email", names)
        self.assertIn("ticketing-webhook", names)

    def test_email_configured_when_host_and_to_set(self):
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.local",
            "ALERT_EMAIL_TO": "ops@example.com",
        }, clear=True):
            channels = {c["channel"]: c for c in notifications.get_notification_channels()}
        self.assertTrue(channels["email"]["configured"])
        self.assertEqual(channels["email"]["target"], "ops@example.com")

    def test_email_not_configured_when_missing_host(self):
        with patch.dict(os.environ, {"ALERT_EMAIL_TO": "ops@example.com"}, clear=True):
            channels = {c["channel"]: c for c in notifications.get_notification_channels()}
        self.assertFalse(channels["email"]["configured"])

    def test_webhook_configured_when_url_set(self):
        with patch.dict(os.environ, {
            "ALERT_TICKETING_WEBHOOK_URL": "https://hooks.local/fraud",
        }, clear=True):
            channels = {c["channel"]: c for c in notifications.get_notification_channels()}
        self.assertTrue(channels["ticketing-webhook"]["configured"])

    def test_webhook_falls_back_to_alert_webhook_url(self):
        with patch.dict(os.environ, {
            "ALERT_WEBHOOK_URL": "https://legacy.local/alerts",
        }, clear=True):
            channels = {c["channel"]: c for c in notifications.get_notification_channels()}
        self.assertTrue(channels["ticketing-webhook"]["configured"])


# ===========================================================================
# notifications.py — send_email_notification
# ===========================================================================

class TestSendEmailNotification(unittest.TestCase):
    def test_skipped_when_smtp_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            result = notifications.send_email_notification({"alert_id": "A-X"})
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["channel"], "email")

    @patch("notifications.smtplib.SMTP")
    def test_sends_with_starttls_and_login(self, smtp_cls):
        srv = MagicMock()
        smtp_cls.return_value.__enter__.return_value = srv

        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.local",
            "SMTP_PORT": "2525",
            "SMTP_USER": "fraud-bot",
            "SMTP_PASSWORD": "secret",
            "ALERT_EMAIL_TO": "ops@example.com",
            "ALERT_EMAIL_FROM": "alerts@example.com",
        }, clear=True):
            result = notifications.send_email_notification({"alert_id": "A-2", "severity": "critical"})

        smtp_cls.assert_called_once_with("smtp.local", 2525, timeout=10)
        srv.starttls.assert_called_once()
        srv.login.assert_called_once_with("fraud-bot", "secret")
        srv.sendmail.assert_called_once()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["target"], "ops@example.com")

    @patch("notifications.smtplib.SMTP")
    def test_sends_without_starttls_when_disabled(self, smtp_cls):
        srv = MagicMock()
        smtp_cls.return_value.__enter__.return_value = srv

        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.local",
            "ALERT_EMAIL_TO": "ops@example.com",
            "SMTP_STARTTLS": "false",
        }, clear=True):
            result = notifications.send_email_notification({"alert_id": "A-3"})

        srv.starttls.assert_not_called()
        self.assertEqual(result["status"], "sent")

    @patch("notifications.smtplib.SMTP")
    def test_sends_without_login_when_no_credentials(self, smtp_cls):
        srv = MagicMock()
        smtp_cls.return_value.__enter__.return_value = srv

        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.local",
            "ALERT_EMAIL_TO": "ops@example.com",
        }, clear=True):
            result = notifications.send_email_notification({"alert_id": "A-6"})

        srv.login.assert_not_called()
        self.assertEqual(result["status"], "sent")

    @patch("notifications.smtplib.SMTP", side_effect=ConnectionRefusedError("refused"))
    def test_smtp_failure_returns_failed(self, _smtp_cls):
        with patch.dict(os.environ, {
            "SMTP_HOST": "bad.host",
            "ALERT_EMAIL_TO": "ops@example.com",
        }, clear=True):
            result = notifications.send_email_notification({"alert_id": "A-7"})

        self.assertEqual(result["status"], "failed")
        self.assertIn("refused", result["detail"])


# ===========================================================================
# notifications.py — send_webhook_notification
# ===========================================================================

class TestSendWebhookNotification(unittest.TestCase):
    def test_skipped_when_url_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            result = notifications.send_webhook_notification({"alert_id": "W-1"})
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["channel"], "ticketing-webhook")

    @patch("notifications.requests.request")
    def test_posts_correct_payload_with_auth_headers(self, req_mock):
        resp = MagicMock()
        resp.status_code = 201
        req_mock.return_value = resp

        alert = {"alert_id": "W-2", "risk_score": 0.98}
        with patch.dict(os.environ, {
            "ALERT_TICKETING_WEBHOOK_URL": "https://tickets.local/hooks/fraud",
            "ALERT_WEBHOOK_METHOD": "post",
            "ALERT_WEBHOOK_TIMEOUT": "15",
            "ALERT_WEBHOOK_HEADERS_JSON": '{"X-Source":"fraud-dashboard"}',
            "ALERT_WEBHOOK_BEARER_TOKEN": "token-123",
        }, clear=True):
            result = notifications.send_webhook_notification(alert)

        req_mock.assert_called_once_with(
            "POST",
            "https://tickets.local/hooks/fraud",
            headers={
                "Content-Type": "application/json",
                "X-Source": "fraud-dashboard",
                "Authorization": "Bearer token-123",
            },
            json={"event_type": "fraud_alert", "alert": alert},
            timeout=15.0,
        )
        resp.raise_for_status.assert_called_once()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["status_code"], 201)

    @patch("notifications.requests.request")
    def test_uses_default_get_method(self, req_mock):
        resp = MagicMock()
        resp.status_code = 200
        req_mock.return_value = resp

        with patch.dict(os.environ, {
            "ALERT_TICKETING_WEBHOOK_URL": "https://hooks.local/ping",
        }, clear=True):
            notifications.send_webhook_notification({"alert_id": "W-3"})

        args, _ = req_mock.call_args
        self.assertEqual(args[0], "POST")  # default method

    @patch("notifications.requests.request", side_effect=RuntimeError("timeout"))
    def test_network_failure_returns_failed(self, _mock):
        with patch.dict(os.environ, {
            "ALERT_WEBHOOK_URL": "https://ops.local/alerts",
        }, clear=True):
            result = notifications.send_webhook_notification({"alert_id": "W-4"})

        self.assertEqual(result["status"], "failed")
        self.assertIn("timeout", result["detail"])

    @patch("notifications.requests.request")
    def test_http_error_returns_failed(self, req_mock):
        import requests as req_lib
        resp = MagicMock()
        resp.status_code = 500
        resp.raise_for_status.side_effect = req_lib.HTTPError("500 Server Error")
        req_mock.return_value = resp

        with patch.dict(os.environ, {
            "ALERT_TICKETING_WEBHOOK_URL": "https://hooks.local/err",
        }, clear=True):
            result = notifications.send_webhook_notification({"alert_id": "W-5"})

        self.assertEqual(result["status"], "failed")


# ===========================================================================
# main.py — _store_recent_alert dedup + ring-buffer
# ===========================================================================

class TestStoreRecentAlert(unittest.TestCase):
    def setUp(self):
        """Import main with confluent_kafka stubbed out so no Kafka connection is made."""
        import types
        if "confluent_kafka" not in sys.modules:
            ck = types.ModuleType("confluent_kafka")
            ck.Consumer = MagicMock()
            ck.KafkaError = MagicMock()
            sys.modules["confluent_kafka"] = ck

        # Patch the src.notifications import path used by main.py
        fake_notif = MagicMock()
        fake_notif.dispatch_notifications.return_value = []
        fake_notif.get_notification_channels.return_value = []
        sys.modules["src.notifications"] = fake_notif

        import importlib
        import main as main_module
        importlib.reload(main_module)
        self.main = main_module

    def tearDown(self):
        self.main.recent_alerts.clear()

    def test_alert_is_stored(self):
        self.main._store_recent_alert({"alert_id": "S-1", "severity": "high"})
        self.assertEqual(len(self.main.recent_alerts), 1)
        self.assertEqual(self.main.recent_alerts[0]["alert_id"], "S-1")

    def test_duplicate_alert_id_is_replaced(self):
        self.main._store_recent_alert({"alert_id": "S-2", "value": "first"})
        self.main._store_recent_alert({"alert_id": "S-2", "value": "second"})
        # Should have exactly one entry with the updated value
        matches = [a for a in self.main.recent_alerts if a["alert_id"] == "S-2"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["value"], "second")

    def test_ring_buffer_evicts_oldest_when_full(self):
        self.main.recent_alerts_max = 5
        for i in range(7):
            self.main._store_recent_alert({"alert_id": f"S-buf-{i}"})
        self.assertLessEqual(len(self.main.recent_alerts), 5)
        # The most recent 5 should be present
        stored_ids = [a["alert_id"] for a in self.main.recent_alerts]
        for i in range(2, 7):
            self.assertIn(f"S-buf-{i}", stored_ids)

    def test_alert_without_id_is_appended(self):
        self.main._store_recent_alert({"severity": "low"})
        self.assertEqual(len(self.main.recent_alerts), 1)


# ===========================================================================
# main.py — FastAPI endpoint tests via TestClient
# ===========================================================================

class TestAlertingAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import types
        if "confluent_kafka" not in sys.modules:
            ck = types.ModuleType("confluent_kafka")
            ck.Consumer = MagicMock()
            ck.KafkaError = MagicMock()
            sys.modules["confluent_kafka"] = ck

        fake_notif = MagicMock()
        fake_notif.dispatch_notifications.return_value = []
        fake_notif.get_notification_channels.return_value = [
            {"channel": "email", "configured": False, "target": None},
            {"channel": "ticketing-webhook", "configured": False, "target": None},
        ]
        sys.modules["src.notifications"] = fake_notif

        import importlib
        import main as main_module
        importlib.reload(main_module)
        cls.main = main_module

    def _client(self):
        from fastapi.testclient import TestClient
        return TestClient(self.main.app, raise_server_exceptions=False)

    def setUp(self):
        self.main.recent_alerts.clear()
        # Reset channel mock to a known unconfigured baseline before every test
        import sys
        fake_notif = sys.modules["src.notifications"]
        fake_notif.get_notification_channels.return_value = [
            {"channel": "email", "configured": False, "target": None},
            {"channel": "ticketing-webhook", "configured": False, "target": None},
        ]

    def test_health_returns_healthy(self):
        resp = self._client().get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "healthy"})

    def test_get_recent_alerts_empty(self):
        resp = self._client().get("/alerts/recent")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_get_recent_alerts_returns_stored(self):
        self.main._store_recent_alert({"alert_id": "API-1", "severity": "critical"})
        self.main._store_recent_alert({"alert_id": "API-2", "severity": "high"})
        resp = self._client().get("/alerts/recent?limit=10")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 2)
        # Most recent first (reversed)
        self.assertEqual(body[0]["alert_id"], "API-2")

    def test_get_recent_alerts_limit_respected(self):
        for i in range(10):
            self.main._store_recent_alert({"alert_id": f"API-lim-{i}"})
        resp = self._client().get("/alerts/recent?limit=3")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 3)

    def test_get_channels_returns_channel_list(self):
        resp = self._client().get("/alerts/channels")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("channels", body)
        self.assertIn("configured_channel_count", body)
        self.assertEqual(body["configured_channel_count"], 0)

    def test_get_channels_counts_configured(self):
        import sys
        fake_notif = sys.modules["src.notifications"]
        fake_notif.get_notification_channels.return_value = [
            {"channel": "email", "configured": True, "target": "ops@example.com"},
            {"channel": "ticketing-webhook", "configured": False, "target": None},
        ]
        resp = self._client().get("/alerts/channels")
        body = resp.json()
        self.assertEqual(body["configured_channel_count"], 1)


if __name__ == "__main__":
    unittest.main()
