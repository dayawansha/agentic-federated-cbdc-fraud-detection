"""
Expanded test suite for transaction-graph service.

Coverage:
  - Unit tests for all GraphService methods (including new centrality + temporal features)
  - Edge-case / empty-account handling
  - FastAPI endpoint integration tests via TestClient
  - Bootstrap integration: insert → query flow using mocked db
"""
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: inject lightweight stubs so we can import without real packages
# ---------------------------------------------------------------------------
SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

if "neo4j" not in sys.modules:
    neo4j_stub = types.ModuleType("neo4j")

    class _GraphDatabase:
        @staticmethod
        def driver(*_args, **_kwargs):
            raise RuntimeError("neo4j driver should not be used in unit tests")

    neo4j_stub.GraphDatabase = _GraphDatabase
    sys.modules["neo4j"] = neo4j_stub

if "pydantic_settings" not in sys.modules:
    settings_stub = types.ModuleType("pydantic_settings")

    class _BaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    settings_stub.BaseSettings = _BaseSettings
    sys.modules["pydantic_settings"] = settings_stub

if "confluent_kafka" not in sys.modules:
    kafka_stub = types.ModuleType("confluent_kafka")
    kafka_stub.Producer = MagicMock()
    sys.modules["confluent_kafka"] = kafka_stub

from services.graph_service import GraphService  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: build a mock session that returns a specific single() record
# ---------------------------------------------------------------------------
def _mock_session_single(mock_db, record):
    mock_session = MagicMock()
    mock_db.get_session.return_value.__enter__.return_value = mock_session
    mock_session.run.return_value.single.return_value = record
    return mock_session


# ===========================================================================
# Unit tests — GraphService
# ===========================================================================

class TestAddTransaction(unittest.TestCase):
    @patch("services.graph_service.db")
    def test_add_transaction_runs_merge_query(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value.single.return_value = None

        tx_data = {
            "transaction_id": "tx001",
            "source_account": "accA",
            "target_account": "accB",
            "amount": 250.0,
            "asset_type": "CBDC",
        }
        result = GraphService.add_transaction(tx_data)

        mock_session.run.assert_called_once()
        args, kwargs = mock_session.run.call_args
        self.assertIn("MERGE (tx:Transaction", args[0])
        self.assertEqual(kwargs["transaction_id"], "tx001")
        self.assertEqual(kwargs["source_account"], "accA")
        # Falls back to tx_data['transaction_id'] when single() is None
        self.assertEqual(result, "tx001")

    @patch("services.graph_service.db")
    def test_add_transaction_returns_db_id(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value.single.return_value = ["tx001"]

        tx_data = {
            "transaction_id": "tx001",
            "source_account": "accA",
            "target_account": "accB",
            "amount": 50.0,
        }
        result = GraphService.add_transaction(tx_data)
        self.assertEqual(result, "tx001")


class TestGetSubgraph(unittest.TestCase):
    @patch("services.graph_service.db")
    def test_get_subgraph_returns_nodes(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        mock_node = MagicMock()
        mock_node.get.return_value = "accA"
        mock_node.labels = ["Account"]
        mock_node.__iter__ = lambda self: iter({})
        mock_node.keys = lambda: []

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda k: [mock_node] if k == "nodes" else []
        mock_session.run.return_value = [mock_record]

        result = GraphService.get_subgraph("accA", depth=1)
        self.assertIn("nodes", result)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["id"], "accA")


class TestGetAllAccounts(unittest.TestCase):
    @patch("services.graph_service.db")
    def test_get_all_accounts_returns_list(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = [
            {"account_id": "accA", "sent_count": 3, "received_count": 1},
            {"account_id": "accB", "sent_count": 0, "received_count": 5},
        ]

        result = GraphService.get_all_accounts(limit=10)

        mock_session.run.assert_called_once()
        _, kwargs = mock_session.run.call_args
        self.assertEqual(kwargs["limit"], 10)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["account_id"], "accA")
        self.assertEqual(result[1]["received_count"], 5)

    @patch("services.graph_service.db")
    def test_get_all_accounts_empty(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []

        result = GraphService.get_all_accounts(limit=50)
        self.assertEqual(result, [])


class TestGetAccountFeatures(unittest.TestCase):
    def _make_base_record(self):
        return {
            "account_id": "accA",
            "sent_count": 2,
            "received_count": 3,
            "total_tx_count": 5,
            "sent_amount_sum": 120.0,
            "received_amount_sum": 80.0,
            "total_amount": 200.0,
            "sent_amount_avg": 60.0,
            "received_amount_avg": 26.666,
            "sent_amount_max": 75.0,
            "received_amount_max": 40.0,
            "sent_counterparties": ["accB", "accC"],
            "received_counterparties": ["accC", "accD"],
            "sent_asset_types": ["CBDC"],
            "received_asset_types": ["CBDC", "TOKEN"],
            "sent_counterparty_count": 2,
            "received_counterparty_count": 2,
            "counterparty_touchpoints": 4,
            "reciprocal_counterparties": 1,
            "two_hop_reach": 6,
        }

    @patch("services.graph_service.GraphService.get_account_temporal_features")
    @patch("services.graph_service.GraphService.get_account_centrality")
    @patch("services.graph_service.db")
    def test_get_account_features_all_fields(self, mock_db, mock_cent, mock_temp):
        mock_session = _mock_session_single(mock_db, self._make_base_record())

        mock_cent.return_value = {
            "account_id": "accA",
            "in_degree": 3,
            "out_degree": 2,
            "two_hop_reach": 6,
            "betweenness_proxy": 0.5,
            "pagerank_approx": 1.2,
        }
        mock_temp.return_value = {
            "account_id": "accA",
            "tx_count_1h": 0,
            "tx_count_24h": 2,
            "tx_count_7d": 5,
            "velocity_7d": 0.029762,
            "burst_ratio": 0.0,
            "first_tx_timestamp": "2026-01-01T00:00:00+00:00",
            "last_tx_timestamp": "2026-06-24T12:00:00+00:00",
        }

        result = GraphService.get_account_features("accA")

        self.assertEqual(result["account_id"], "accA")
        self.assertEqual(result["total_tx_count"], 5)
        self.assertEqual(result["counterparty_diversity"], 3)  # {accB,accC} | {accC,accD}
        self.assertEqual(result["reciprocal_counterparties"], 1)
        self.assertEqual(result["unique_asset_types"], 2)
        self.assertAlmostEqual(result["net_flow"], -40.0)
        self.assertAlmostEqual(result["avg_amount"], 40.0)
        self.assertAlmostEqual(result["in_out_ratio"], 1.5)
        # Centrality fields merged
        self.assertEqual(result["in_degree"], 3)
        self.assertEqual(result["out_degree"], 2)
        self.assertAlmostEqual(result["pagerank_approx"], 1.2)
        self.assertAlmostEqual(result["betweenness_proxy"], 0.5)
        # Temporal fields merged
        self.assertEqual(result["tx_count_7d"], 5)
        self.assertEqual(result["tx_count_1h"], 0)
        self.assertAlmostEqual(result["velocity_7d"], 0.029762)
        self.assertEqual(result["first_tx_timestamp"], "2026-01-01T00:00:00+00:00")

    @patch("services.graph_service.GraphService.get_account_temporal_features")
    @patch("services.graph_service.GraphService.get_account_centrality")
    @patch("services.graph_service.db")
    def test_get_account_features_empty_account(self, mock_db, mock_cent, mock_temp):
        """When Neo4j returns no record, all fields default to zero/None."""
        mock_session = _mock_session_single(mock_db, None)
        mock_cent.return_value = {}
        mock_temp.return_value = {}

        result = GraphService.get_account_features("unknown_acc")

        self.assertEqual(result["account_id"], "unknown_acc")
        self.assertEqual(result["total_tx_count"], 0)
        self.assertAlmostEqual(result["net_flow"], 0.0)
        self.assertIn("pagerank_approx", result)
        self.assertIn("tx_count_1h", result)
        self.assertIn("burst_ratio", result)


class TestGetAccountCentrality(unittest.TestCase):
    @patch("services.graph_service.db")
    def test_centrality_happy_path(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        deg_record = {"out_degree": 4, "in_degree": 7}
        bet_record = {"two_hop_reach": 12, "betweenness_proxy": 0.417}
        pr_record  = {"pagerank_approx": 2.35}

        # Three sequential session.run() calls
        mock_session.run.return_value.single.side_effect = [
            deg_record, bet_record, pr_record
        ]

        result = GraphService.get_account_centrality("accA")

        self.assertEqual(result["account_id"], "accA")
        self.assertEqual(result["in_degree"], 7)
        self.assertEqual(result["out_degree"], 4)
        self.assertEqual(result["two_hop_reach"], 12)
        self.assertAlmostEqual(result["betweenness_proxy"], 0.417)
        self.assertAlmostEqual(result["pagerank_approx"], 2.35)

    @patch("services.graph_service.db")
    def test_centrality_unknown_account_returns_zeros(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        # degree query returns None → method should short-circuit and return zero dict
        mock_session.run.return_value.single.return_value = None

        result = GraphService.get_account_centrality("ghost_acc")

        self.assertEqual(result["account_id"], "ghost_acc")
        self.assertEqual(result["in_degree"], 0)
        self.assertEqual(result["out_degree"], 0)
        self.assertAlmostEqual(result["pagerank_approx"], 0.0)

    @patch("services.graph_service.db")
    def test_centrality_null_pagerank(self, mock_db):
        """pagerank_approx IS NULL in Neo4j (no senders) → should return 0.0."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value.single.side_effect = [
            {"out_degree": 2, "in_degree": 0},
            {"two_hop_reach": 2, "betweenness_proxy": 0.0},
            {"pagerank_approx": None},
        ]

        result = GraphService.get_account_centrality("accX")
        self.assertAlmostEqual(result["pagerank_approx"], 0.0)


class TestGetAccountTemporalFeatures(unittest.TestCase):
    @patch("services.graph_service.db")
    def test_temporal_happy_path(self, mock_db):
        now = datetime.now(tz=timezone.utc)
        ts_recent = (now - timedelta(minutes=30)).isoformat()  # within 1h, 24h, 7d
        ts_day    = (now - timedelta(hours=12)).isoformat()     # within 24h, 7d only
        ts_week   = (now - timedelta(days=3)).isoformat()       # within 7d only

        temporal_record = {
            "tx_count_1h": 1,
            "tx_count_24h": 2,
            "tx_count_7d": 3,
            "first_tx_timestamp": ts_week,
            "last_tx_timestamp": ts_recent,
        }

        mock_session = _mock_session_single(mock_db, temporal_record)

        result = GraphService.get_account_temporal_features("accA")

        self.assertEqual(result["tx_count_1h"], 1)
        self.assertEqual(result["tx_count_24h"], 2)
        self.assertEqual(result["tx_count_7d"], 3)
        self.assertAlmostEqual(result["velocity_7d"], 3 / (7 * 24), places=5)
        self.assertAlmostEqual(result["burst_ratio"], 1 / 2, places=5)
        self.assertEqual(result["first_tx_timestamp"], ts_week)
        self.assertEqual(result["last_tx_timestamp"], ts_recent)

    @patch("services.graph_service.db")
    def test_temporal_no_data_returns_zeros(self, mock_db):
        _mock_session_single(mock_db, None)
        result = GraphService.get_account_temporal_features("new_acc")
        self.assertEqual(result["tx_count_1h"], 0)
        self.assertEqual(result["tx_count_7d"], 0)
        self.assertAlmostEqual(result["velocity_7d"], 0.0)
        self.assertAlmostEqual(result["burst_ratio"], 0.0)
        self.assertIsNone(result["first_tx_timestamp"])

    @patch("services.graph_service.db")
    def test_temporal_zero_24h_avoids_division(self, mock_db):
        """burst_ratio should not raise ZeroDivisionError when tx_count_24h == 0."""
        temporal_record = {
            "tx_count_1h": 0,
            "tx_count_24h": 0,
            "tx_count_7d": 0,
            "first_tx_timestamp": None,
            "last_tx_timestamp": None,
        }
        _mock_session_single(mock_db, temporal_record)

        result = GraphService.get_account_temporal_features("accY")
        self.assertAlmostEqual(result["burst_ratio"], 0.0)


# ===========================================================================
# API integration tests — FastAPI TestClient
# ===========================================================================

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Import FastAPI app once with the db and cdc_service fully mocked so
        that no real Neo4j / Kafka connection is made.
        """
        with (
            patch("services.graph_service.db"),
            patch("services.cdc_service.cdc_service"),
        ):
            # Import the app module; it imports graph_service which already has
            # db patched at module level via the context manager above.
            import importlib
            import main as app_module
            importlib.reload(app_module)
            cls.app_module = app_module

    def _client(self):
        from fastapi.testclient import TestClient
        return TestClient(self.app_module.app, raise_server_exceptions=False)

    def test_health_endpoint(self):
        client = self._client()
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "healthy"})

    @patch("services.graph_service.GraphService.add_transaction", return_value="tx_api_01")
    @patch("services.cdc_service.cdc_service")
    def test_post_transaction_endpoint(self, _mock_cdc, _mock_add):
        client = self._client()
        payload = {
            "transaction_id": "tx_api_01",
            "source_account": "accA",
            "target_account": "accB",
            "amount": 500.0,
            "asset_type": "CBDC",
        }
        resp = client.post("/transactions", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["transaction_id"], "tx_api_01")

    @patch("services.graph_service.GraphService.get_all_accounts", return_value=[
        {"account_id": "accA", "sent_count": 2, "received_count": 1},
    ])
    def test_get_all_accounts_endpoint(self, _mock):
        client = self._client()
        resp = client.get("/accounts")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("accounts", body)
        self.assertEqual(len(body["accounts"]), 1)
        self.assertEqual(body["count"], 1)

    @patch("services.graph_service.GraphService.get_account_features", return_value={
        "account_id": "accA", "total_tx_count": 5, "pagerank_approx": 1.2,
        "tx_count_1h": 0, "velocity_7d": 0.029,
    })
    def test_get_account_features_endpoint(self, _mock):
        client = self._client()
        resp = client.get("/accounts/accA/features")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["account_id"], "accA")
        self.assertEqual(body["total_tx_count"], 5)
        self.assertIn("pagerank_approx", body)
        self.assertIn("velocity_7d", body)

    @patch("services.graph_service.GraphService.get_account_centrality", return_value={
        "account_id": "accA", "in_degree": 3, "out_degree": 2,
        "two_hop_reach": 8, "betweenness_proxy": 0.375, "pagerank_approx": 1.5,
    })
    def test_get_account_centrality_endpoint(self, _mock):
        client = self._client()
        resp = client.get("/accounts/accA/centrality")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["account_id"], "accA")
        self.assertIn("pagerank_approx", body)
        self.assertIn("betweenness_proxy", body)
        self.assertEqual(body["in_degree"], 3)

    @patch("services.graph_service.GraphService.get_account_temporal_features", return_value={
        "account_id": "accA", "tx_count_1h": 2, "tx_count_24h": 10,
        "tx_count_7d": 30, "velocity_7d": 0.178, "burst_ratio": 0.2,
        "first_tx_timestamp": "2026-06-17T00:00:00+00:00",
        "last_tx_timestamp": "2026-06-24T10:00:00+00:00",
    })
    def test_get_account_temporal_endpoint(self, _mock):
        client = self._client()
        resp = client.get("/accounts/accA/temporal")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["account_id"], "accA")
        self.assertIn("tx_count_1h", body)
        self.assertIn("velocity_7d", body)
        self.assertEqual(body["tx_count_24h"], 10)


# ===========================================================================
# Bootstrap integration test — insert → query flow (mocked db)
# ===========================================================================

class TestBootstrapInsertThenQuery(unittest.TestCase):
    """
    Simulates the flow: load two transactions via add_transaction, then verify
    get_account_features returns the expected aggregated totals.
    """

    @patch("services.graph_service.GraphService.get_account_temporal_features")
    @patch("services.graph_service.GraphService.get_account_centrality")
    @patch("services.graph_service.db")
    def test_insert_then_query(self, mock_db, mock_cent, mock_temp):
        # ----- Insert phase -----
        insert_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = insert_session
        insert_session.run.return_value.single.return_value = None

        tx_a = {"transaction_id": "txI1", "source_account": "bankX",
                 "target_account": "bankY", "amount": 1000.0, "asset_type": "CBDC"}
        tx_b = {"transaction_id": "txI2", "source_account": "bankX",
                 "target_account": "bankZ", "amount": 500.0, "asset_type": "CBDC"}

        GraphService.add_transaction(tx_a)
        GraphService.add_transaction(tx_b)
        self.assertEqual(insert_session.run.call_count, 2)

        # ----- Query phase -----
        query_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = query_session

        # Simulate Neo4j returning aggregated sums for bankX (2 sends, total 1500)
        query_record = {
            "account_id": "bankX",
            "sent_count": 2,
            "received_count": 0,
            "total_tx_count": 2,
            "sent_amount_sum": 1500.0,
            "received_amount_sum": 0.0,
            "total_amount": 1500.0,
            "sent_amount_avg": 750.0,
            "received_amount_avg": 0.0,
            "sent_amount_max": 1000.0,
            "received_amount_max": 0.0,
            "sent_counterparties": ["bankY", "bankZ"],
            "received_counterparties": [],
            "sent_asset_types": ["CBDC"],
            "received_asset_types": [],
            "sent_counterparty_count": 2,
            "received_counterparty_count": 0,
            "counterparty_touchpoints": 2,
            "reciprocal_counterparties": 0,
            "two_hop_reach": 2,
        }
        query_session.run.return_value.single.return_value = query_record

        mock_cent.return_value = {
            "account_id": "bankX", "in_degree": 0, "out_degree": 2,
            "two_hop_reach": 2, "betweenness_proxy": 0.0, "pagerank_approx": 0.0,
        }
        mock_temp.return_value = {
            "account_id": "bankX", "tx_count_1h": 0, "tx_count_24h": 0,
            "tx_count_7d": 0, "velocity_7d": 0.0, "burst_ratio": 0.0,
            "first_tx_timestamp": None, "last_tx_timestamp": None,
        }

        features = GraphService.get_account_features("bankX")

        self.assertEqual(features["account_id"], "bankX")
        self.assertEqual(features["sent_count"], 2)
        self.assertEqual(features["received_count"], 0)
        self.assertAlmostEqual(features["sent_amount_sum"], 1500.0)
        self.assertAlmostEqual(features["total_amount"], 1500.0)
        self.assertAlmostEqual(features["avg_amount"], 750.0)
        self.assertAlmostEqual(features["net_flow"], -1500.0)
        self.assertEqual(features["counterparty_diversity"], 2)
        # Centrality + temporal still present and correct
        self.assertEqual(features["out_degree"], 2)
        self.assertEqual(features["tx_count_7d"], 0)


class TestExportTensors(unittest.TestCase):
    @patch("services.graph_service.GraphService.get_account_features")
    @patch("services.graph_service.db")
    def test_export_tensors_returns_expected_format(self, mock_db, mock_account_features):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        mock_account_features.side_effect = [
            {
                "total_tx_count": 5,
                "total_amount": 140.0,
                "avg_amount": 28.0,
                "counterparty_diversity": 3,
                "reciprocal_counterparties": 1,
                "two_hop_reach": 6,
                "in_degree": 2,
                "out_degree": 5,
                "betweenness_proxy": 0.4,
                "pagerank_approx": 1.2,
                "tx_count_1h": 1,
                "tx_count_24h": 2,
                "tx_count_7d": 5,
                "velocity_7d": 0.03,
                "burst_ratio": 0.5,
                "net_flow": -60.0,
                "in_out_ratio": 0.4,
            },
            {
                "total_tx_count": 4,
                "total_amount": 90.0,
                "avg_amount": 22.5,
                "counterparty_diversity": 2,
                "reciprocal_counterparties": 0,
                "two_hop_reach": 4,
                "in_degree": 4,
                "out_degree": 1,
                "betweenness_proxy": 0.2,
                "pagerank_approx": 0.7,
                "tx_count_1h": 0,
                "tx_count_24h": 1,
                "tx_count_7d": 4,
                "velocity_7d": 0.02,
                "burst_ratio": 0.0,
                "net_flow": 45.0,
                "in_out_ratio": 4.0,
            },
        ]

        mock_record_node = {
            "tx_id": "tx-1",
            "source_account_id": "acct-src",
            "target_account_id": "acct-tgt",
            "amount": 100.0,
            "asset_type": "CBDC",
            "timestamp": "2026-06-24T12:00:00+00:00",
        }
        mock_record_edge = {
            "source": "tx-1",
            "target": "tx-1"
        }

        mock_session.run.side_effect = [
            [mock_record_node],
            [mock_record_edge],
        ]

        result = GraphService.export_tensors()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["node_type"], "transaction")
        self.assertEqual(result["node_ids"], ["tx-1"])
        self.assertEqual(len(result["x"]), 1)
        self.assertEqual(len(result["x"][0]), len(GraphService.TRANSACTION_EXPORT_FEATURE_NAMES))
        self.assertEqual(result["x"][0][0], 100.0)
        self.assertEqual(result["feature_names"], GraphService.TRANSACTION_EXPORT_FEATURE_NAMES)
        self.assertEqual(result["edge_index"], [[0], [0]])

    @patch("services.graph_service.db")
    def test_export_tensors_handles_database_errors_gracefully(self, mock_db):
        mock_db.get_session.side_effect = Exception("Neo4j is down")
        result = GraphService.export_tensors()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["node_ids"], [])
        self.assertEqual(result["x"], [])
        self.assertEqual(result["edge_index"], [[], []])


class TestExportTensorsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app
        from fastapi.testclient import TestClient
        cls.client = TestClient(app)

    @patch("main.graph_service")
    def test_export_tensors_endpoint(self, mock_service):
        mock_service.export_tensors.return_value = {
            "status": "success",
            "node_type": "transaction",
            "feature_schema_version": 2,
            "feature_names": ["tx_amount"],
            "node_ids": ["tx-1"],
            "x": [[1.0, 2.0]],
            "edge_index": [[0], [0]]
        }
        response = self.client.get("/graph/export-tensors")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["node_ids"], ["tx-1"])


if __name__ == "__main__":
    unittest.main()
