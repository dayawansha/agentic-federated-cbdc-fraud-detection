import base64
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SRC = SERVICE_ROOT / "src"

for path in (str(SERVICE_ROOT.parents[2]), str(SERVICE_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from langgraph.graph import END, StateGraph  # type: ignore
except ModuleNotFoundError:
    graph_module = types.ModuleType("langgraph.graph")

    class _CompiledGraph:
        async def ainvoke(self, state):
            return state

    class StateGraph:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            self._compiled = _CompiledGraph()

        def add_node(self, *_args, **_kwargs):
            return None

        def set_entry_point(self, *_args, **_kwargs):
            return None

        def add_edge(self, *_args, **_kwargs):
            return None

        def compile(self):
            return self._compiled

    END = "END"
    graph_module.END = END
    graph_module.StateGraph = StateGraph
    langgraph_module = types.ModuleType("langgraph")
    langgraph_module.graph = graph_module
    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module

import main


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = main.httpx.Request("POST", "http://local-gnn/infer")
            response = main.httpx.Response(self.status_code, request=request, text=self.text)
            raise main.httpx.HTTPStatusError("request failed", request=request, response=response)

class FakeGetResponse(FakeResponse):
    def raise_for_status(self):
        if self.status_code >= 400:
            request = main.httpx.Request("GET", "http://model-registry/models/latest/weights")
            response = main.httpx.Response(self.status_code, request=request, text=self.text)
            raise main.httpx.HTTPStatusError("request failed", request=request, response=response)


class FakeAsyncClient:
    def __init__(self, response=None, error=None, get_response=None, get_error=None):
        self.response = response
        self.error = error
        self.get_response = get_response
        self.get_error = get_error
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.response

    async def get(self, url, timeout=None):
        self.calls.append({"method": "GET", "url": url, "timeout": timeout})
        if self.get_error is not None:
            raise self.get_error
        return self.get_response


class TestLocalAgent(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main.agent_status.update(
            {
                "agent_id": "local-agent",
                "last_round_id": None,
                "last_update_at": None,
                "last_metrics": {},
                "last_model_version": None,
                "last_inference_at": None,
                "last_inference_summary": {},
            }
        )

    async def test_fetch_latest_global_model_loads_weights_when_registry_has_model(self):
        encoded = base64.b64encode(b"global-model").decode("ascii")
        client = FakeAsyncClient(get_response=FakeGetResponse({"version_id": "v-1", "weights": encoded}))
        state = {
            "agent_id": "agent-1",
            "round_id": "round-1",
            "data_ready": True,
            "global_model_loaded": False,
            "training_complete": False,
            "privacy_applied": False,
            "raw_weights": b"",
            "protected_weights": b"",
            "encrypted_weights": b"",
            "sample_size": 0,
            "metrics": {},
            "global_weights": b"",
            "model_version_id": None,
            "noise_multiplier": 0.01,
            "current_step": "global_model_fetch",
        }

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            result = await main.fetch_latest_global_model(state)

        self.assertTrue(result["global_model_loaded"])
        self.assertEqual(result["global_weights"], b"global-model")
        self.assertEqual(result["model_version_id"], "v-1")
        self.assertEqual(result["current_step"], "training_triggered")

    async def test_fetch_inference_predictions_updates_status_summary(self):
        payload = {
            "predictions": [
                {
                    "tx_id": 101,
                    "predicted_class": "illicit",
                    "predicted_label": 1,
                    "confidence": 0.99,
                    "illicit_probability": 0.99,
                    "licit_probability": 0.01,
                    "unknown_probability": 0.0,
                    "known_label": "unknown",
                },
                {
                    "tx_id": 102,
                    "predicted_class": "licit",
                    "predicted_label": 0,
                    "confidence": 0.75,
                    "illicit_probability": 0.2,
                    "licit_probability": 0.75,
                    "unknown_probability": 0.05,
                    "known_label": "licit",
                },
            ]
        }
        client = FakeAsyncClient(response=FakeResponse(payload))

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            result = await main.fetch_inference_predictions(limit=500, tx_ids=[7, "9"])

        self.assertEqual(result.prediction_count, 2)
        self.assertEqual(result.predictions[0].tx_id, 101)
        self.assertEqual(client.calls[0]["json"]["limit"], 50)
        self.assertEqual(client.calls[0]["json"]["tx_ids"], [7, 9])
        self.assertEqual(main.agent_status["last_inference_summary"]["prediction_count"], 2)
        self.assertEqual(main.agent_status["last_inference_summary"]["high_risk_count"], 1)
        self.assertEqual(main.agent_status["last_inference_summary"]["top_tx_id"], 101)

    async def test_fetch_inference_predictions_raises_502_when_service_unreachable(self):
        client = FakeAsyncClient(error=RuntimeError("network down"))

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(main.HTTPException) as exc:
                await main.fetch_inference_predictions(limit=3)

        self.assertEqual(exc.exception.status_code, 502)
        self.assertEqual(exc.exception.detail, "Local GNN inference service unreachable")

    async def test_start_local_round_updates_agent_status(self):
        final_state = {
            "agent_id": "agent-1",
            "round_id": "round-7",
            "current_step": "done",
            "data_ready": True,
            "global_model_loaded": True,
            "training_complete": True,
            "privacy_applied": True,
            "sample_size": 12,
            "model_version_id": "v-round-6",
            "metrics": {"loss": 0.11},
        }

        class FakeGraph:
            async def ainvoke(self, _state):
                return final_state

        with patch.object(main, "app_graph", FakeGraph()):
            response = await main.start_local_round(round_id="round-7", agent_id="agent-1")

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["final_state"]["current_step"], "done")
        self.assertTrue(response["final_state"]["global_model_loaded"])
        self.assertEqual(response["final_state"]["model_version_id"], "v-round-6")
        self.assertEqual(main.agent_status["agent_id"], "agent-1")
        self.assertEqual(main.agent_status["last_round_id"], "round-7")
        self.assertEqual(main.agent_status["last_model_version"], "v-round-6")
        self.assertEqual(main.agent_status["last_metrics"], {"loss": 0.11})
        self.assertIsNotNone(main.agent_status["last_update_at"])

    async def test_build_alerts_from_predictions_filters_for_high_confidence_illicit_results(self):
        predictions = [
            main.AgentInferencePrediction(
                tx_id=101,
                predicted_class="illicit",
                predicted_label=1,
                confidence=0.97,
                illicit_probability=0.97,
                licit_probability=0.02,
                unknown_probability=0.01,
                known_label="unknown",
            ),
            main.AgentInferencePrediction(
                tx_id=102,
                predicted_class="licit",
                predicted_label=0,
                confidence=0.99,
                illicit_probability=0.01,
                licit_probability=0.99,
                unknown_probability=0.0,
                known_label="licit",
            ),
            main.AgentInferencePrediction(
                tx_id=103,
                predicted_class="illicit",
                predicted_label=1,
                confidence=0.40,
                illicit_probability=0.40,
                licit_probability=0.55,
                unknown_probability=0.05,
                known_label="unknown",
            ),
        ]

        alerts = main._build_alerts_from_predictions("agent-1", predictions)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["txId"], 101)
        self.assertEqual(alerts[0]["agent_id"], "agent-1")
        self.assertEqual(alerts[0]["source"], "local-agent-inference")


if __name__ == "__main__":
    unittest.main()
