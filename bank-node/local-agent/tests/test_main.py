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
from shared.schemas.models import WeightNegotiationItem


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
    def __init__(self, response=None, error=None, get_response=None, get_error=None, get_responses=None):
        self.response = response
        self.error = error
        self.get_response = get_response
        self.get_error = get_error
        self.get_responses = get_responses or {}
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
        if url in self.get_responses:
            response = self.get_responses[url]
            if isinstance(response, Exception):
                raise response
            return response
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
                "last_adaptive_plan": {},
                "last_reasoning_trace": [],
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
        self.assertEqual(result["current_step"], "planning")

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

    async def test_fetch_inference_predictions_normalizes_null_numeric_fields(self):
        payload = {
            "predictions": [
                {
                    "tx_id": 301,
                    "predicted_class": "unknown",
                    "predicted_label": 2,
                    "confidence": None,
                    "illicit_probability": None,
                    "licit_probability": None,
                    "unknown_probability": None,
                    "known_label": None,
                }
            ]
        }
        client = FakeAsyncClient(response=FakeResponse(payload))

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            result = await main.fetch_inference_predictions(limit=5)

        self.assertEqual(result.prediction_count, 1)
        self.assertEqual(result.predictions[0].tx_id, 301)
        self.assertEqual(result.predictions[0].confidence, 0.0)
        self.assertEqual(result.predictions[0].illicit_probability, 0.0)
        self.assertEqual(result.predictions[0].licit_probability, 0.0)
        self.assertEqual(result.predictions[0].unknown_probability, 0.0)

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
            "adaptive_plan": {"local_epochs": 2, "noise_multiplier": 0.02},
            "reasoning_trace": ["Recent model quality is weak, so the plan allocates extra local epochs."],
        }

        class FakeGraph:
            async def ainvoke(self, _state):
                return final_state

        client = FakeAsyncClient(
            get_response=FakeGetResponse({"version_id": "v-round-6", "metrics": {"loss": 0.11}})
        )
        with patch.object(main, "app_graph", FakeGraph()):
            with patch.object(main.httpx, "AsyncClient", return_value=client):
                response = await main.start_local_round(round_id="round-7", agent_id="agent-1")

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["final_state"]["current_step"], "done")
        self.assertTrue(response["final_state"]["global_model_loaded"])
        self.assertEqual(response["final_state"]["model_version_id"], "v-round-6")
        self.assertEqual(main.agent_status["agent_id"], "agent-1")
        self.assertEqual(main.agent_status["last_round_id"], "round-7")
        self.assertEqual(main.agent_status["last_model_version"], "v-round-6")
        self.assertEqual(main.agent_status["last_metrics"], {"loss": 0.11})
        self.assertEqual(main.agent_status["last_adaptive_plan"], {"local_epochs": 2, "noise_multiplier": 0.02})
        self.assertEqual(len(main.agent_status["last_reasoning_trace"]), 1)
        self.assertIsNotNone(main.agent_status["last_update_at"])

    async def test_plan_local_execution_adapts_to_sparse_labels_and_low_accuracy(self):
        main.agent_status["last_metrics"] = {"accuracy": 0.45, "loss": 1.1, "labeled_ratio": 0.2, "sparse_label_mode": 1.0}
        main.agent_status["last_inference_summary"] = {"high_risk_count": 3, "top_confidence": 0.97}
        state = {
            "agent_id": "agent-1",
            "round_id": "round-plan",
            "data_ready": True,
            "global_model_loaded": True,
            "training_complete": False,
            "privacy_applied": False,
            "raw_weights": b"",
            "protected_weights": b"",
            "masked_weights": b"",
            "encrypted_weights": b"",
            "encrypted_mask_share": "",
            "protected_payload_sha256": "",
            "encrypted_payload_sha256": "",
            "sample_size": 0,
            "metrics": {},
            "global_weights": b"global-model",
            "model_version_id": "v-2",
            "noise_multiplier": 0.01,
            "selected_strategy": "FedAvg",
            "local_training_strategy": "FedAvg",
            "fedprox_mu": 1.0,
            "local_epochs": 1,
            "pseudo_label_weight": 0.0,
            "pseudo_label_confidence": 0.9,
            "post_round_inference_limit": 5,
            "run_post_round_inference": True,
            "participation_checks": {
                "privacy_budget": {"epsilon": 10.0, "remaining_epsilon": 1.5, "required_reserve_epsilon": 0.5},
                "policy_constraints": {"min_noise_multiplier": 0.0, "max_noise_multiplier": 0.2},
            },
            "adaptive_plan": {},
            "reasoning_trace": [],
            "current_step": "planning",
        }

        result = await main.plan_local_execution(state)

        self.assertEqual(result["current_step"], "training_triggered")
        self.assertEqual(result["local_training_strategy"], "FedProxGNN")
        self.assertGreaterEqual(result["local_epochs"], 2)
        self.assertGreater(result["pseudo_label_weight"], 0.0)
        self.assertTrue(result["run_post_round_inference"])
        self.assertGreater(len(result["reasoning_trace"]), 0)

    async def test_run_local_training_forwards_strategy_and_fedprox_mu(self):
        client = FakeAsyncClient(
            response=FakeResponse(
                {
                    "weights": base64.b64encode(b"trained").decode("ascii"),
                    "sample_size": 9,
                    "metrics": {"loss": 0.21, "fedprox_penalty": 0.03},
                }
            )
        )
        state = {
            "agent_id": "agent-1",
            "round_id": "round-fedprox",
            "data_ready": True,
            "global_model_loaded": True,
            "training_complete": False,
            "privacy_applied": False,
            "raw_weights": b"",
            "protected_weights": b"",
            "masked_weights": b"",
            "encrypted_weights": b"",
            "encrypted_mask_share": "",
            "protected_payload_sha256": "",
            "encrypted_payload_sha256": "",
            "sample_size": 0,
            "metrics": {},
            "global_weights": b"global-model",
            "model_version_id": "v-1",
            "noise_multiplier": 0.01,
            "selected_strategy": "FedProxGNN",
            "local_training_strategy": "FedProxGNN",
            "fedprox_mu": 0.75,
            "local_epochs": 3,
            "pseudo_label_weight": 0.4,
            "pseudo_label_confidence": 0.82,
            "post_round_inference_limit": 8,
            "run_post_round_inference": True,
            "participation_checks": {},
            "adaptive_plan": {"risk_pressure": 0.7, "budget_pressure": 0.2, "sparse_label_pressure": 0.5, "plan_confidence": 0.9},
            "reasoning_trace": ["Sparse labels were detected, so the plan enables semi-supervised pseudo-label training."],
            "current_step": "training_triggered",
        }

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            result = await main.run_local_training(state)

        self.assertTrue(result["training_complete"])
        self.assertEqual(result["sample_size"], 9)
        self.assertEqual(result["metrics"]["fedprox_penalty"], 0.03)
        self.assertEqual(client.calls[0]["json"]["strategy"], "FedProxGNN")
        self.assertEqual(client.calls[0]["json"]["fedprox_mu"], 0.75)
        self.assertEqual(client.calls[0]["json"]["epochs"], 3)
        self.assertEqual(client.calls[0]["json"]["pseudo_label_weight"], 0.4)
        self.assertEqual(client.calls[0]["json"]["pseudo_label_confidence"], 0.82)
        self.assertEqual(base64.b64decode(client.calls[0]["json"]["global_weights"]), b"global-model")

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

    async def test_propose_weights_calculates_correct_ratios(self):
        req = main.WeightNegotiationRequest(
            round_id="round-test",
            agents=[
                WeightNegotiationItem(
                    agent_id="agent-a",
                    sample_size=10,
                    reliability_score=0.9,
                    metrics={"f1_score": 0.8}
                ),
                WeightNegotiationItem(
                    agent_id="agent-b",
                    sample_size=20,
                    reliability_score=1.0,
                    metrics={"f1_score": 0.9}
                )
            ]
        )
        # score A = 10 * 0.8 * 0.9 = 7.2
        # score B = 20 * 0.9 * 1.0 = 18.0
        # total = 25.2
        # weight A = 7.2 / 25.2 = 0.2857...
        # weight B = 18.0 / 25.2 = 0.7142...
        resp = await main.propose_weights(req)
        self.assertEqual(resp.agent_id, "local-agent")
        self.assertAlmostEqual(resp.proposed_weights["agent-a"], 7.2 / 25.2, places=4)
        self.assertAlmostEqual(resp.proposed_weights["agent-b"], 18.0 / 25.2, places=4)

    async def test_evaluate_pattern_approves_valid_ranges(self):
        proposal = main.FraudPatternProposal(
            proposal_id="prop-1",
            proposer_id="agent-b",
            pattern_name="High Velocity",
            feature_indicators={
                "transaction_velocity_threshold": 12.5,
                "risk_score_threshold": 0.85
            },
            rationale="Test"
        )
        vote = await main.evaluate_pattern(proposal)
        self.assertEqual(vote.vote, "APPROVE")
        self.assertIn("indicators are within valid", vote.reason)

    async def test_evaluate_pattern_rejects_out_of_bounds(self):
        proposal = main.FraudPatternProposal(
            proposal_id="prop-2",
            proposer_id="agent-b",
            pattern_name="Invalid Risk Score",
            feature_indicators={
                "risk_score_threshold": 1.5
            },
            rationale="Test"
        )
        vote = await main.evaluate_pattern(proposal)
        self.assertEqual(vote.vote, "REJECT")
        self.assertIn("out of bounds", vote.reason)


class TestAgentSafeguards(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._orig_enforce = main.ENFORCE_PRIVACY_BUDGET
        self._orig_simulate = main.SIMULATE_LOW_RESOURCES
        self._orig_cpu = main.SIMULATE_CPU_LOAD
        self._orig_battery = main.SIMULATE_BATTERY_LEVEL
        self._orig_projected_eps = main.PROJECTED_ROUND_EPSILON_SPEND
        self._orig_projected_delta = main.PROJECTED_ROUND_DELTA_SPEND
        self._orig_min_buffer = main.MIN_REMAINING_EPSILON_BUFFER
        self._orig_min_ratio = main.MIN_REMAINING_EPSILON_RATIO
        self._orig_require_pm = main.REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION
        self._orig_dp_noise = main.DP_NOISE_MULTIPLIER

    async def asyncTearDown(self):
        main.ENFORCE_PRIVACY_BUDGET = self._orig_enforce
        main.SIMULATE_LOW_RESOURCES = self._orig_simulate
        main.SIMULATE_CPU_LOAD = self._orig_cpu
        main.SIMULATE_BATTERY_LEVEL = self._orig_battery
        main.PROJECTED_ROUND_EPSILON_SPEND = self._orig_projected_eps
        main.PROJECTED_ROUND_DELTA_SPEND = self._orig_projected_delta
        main.MIN_REMAINING_EPSILON_BUFFER = self._orig_min_buffer
        main.MIN_REMAINING_EPSILON_RATIO = self._orig_min_ratio
        main.REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION = self._orig_require_pm
        main.DP_NOISE_MULTIPLIER = self._orig_dp_noise

    async def test_start_round_restarts_when_safeguards_disabled(self):
        class FakeGraph:
            async def ainvoke(self, _state):
                return {"current_step": "done"}
        main.ENFORCE_PRIVACY_BUDGET = False
        main.SIMULATE_LOW_RESOURCES = False
        client = FakeAsyncClient(
            get_response=FakeGetResponse({}, status_code=404)
        )
        with patch.object(main, "app_graph", FakeGraph()):
            with patch.object(main.httpx, "AsyncClient", return_value=client):
                resp = await main.start_local_round(round_id="r1", agent_id="agent-1")
        self.assertEqual(resp["status"], "success")

    async def test_start_round_rejected_due_to_privacy_budget(self):
        main.ENFORCE_PRIVACY_BUDGET = True
        main.SIMULATE_LOW_RESOURCES = False
        
        budget_payload = {
            "epsilon": 10.0,
            "delta": 1e-5,
            "total_spent_epsilon": 10.0,
            "total_spent_delta": 0.0
        }
        client = FakeAsyncClient(
            get_responses={
                f"{main.POLICY_MANAGER_URL}/policies/budget/agent-1": FakeGetResponse(budget_payload),
                f"{main.POLICY_MANAGER_URL}/policies/global": FakeGetResponse({"min_noise_multiplier": 0.0, "max_noise_multiplier": 1.0}),
            }
        )
        
        with patch.object(main.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(main.HTTPException) as exc:
                await main.start_local_round(round_id="r1", agent_id="agent-1")
                
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail, "Participation rejected: Insufficient privacy budget for projected round cost")

    async def test_start_round_rejected_when_privacy_reserve_buffer_would_be_breached(self):
        main.ENFORCE_PRIVACY_BUDGET = True
        main.SIMULATE_LOW_RESOURCES = False
        main.PROJECTED_ROUND_EPSILON_SPEND = 0.1
        main.MIN_REMAINING_EPSILON_BUFFER = 0.2

        budget_payload = {
            "epsilon": 1.0,
            "delta": 1e-5,
            "total_spent_epsilon": 0.75,
            "total_spent_delta": 0.0,
        }
        client = FakeAsyncClient(
            get_responses={
                f"{main.POLICY_MANAGER_URL}/policies/budget/agent-1": FakeGetResponse(budget_payload),
                f"{main.POLICY_MANAGER_URL}/policies/global": FakeGetResponse({"min_noise_multiplier": 0.0, "max_noise_multiplier": 1.0}),
            }
        )

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(main.HTTPException) as exc:
                await main.start_local_round(round_id="r1", agent_id="agent-1")

        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail, "Participation rejected: Privacy reserve would fall below policy buffer")

    async def test_start_round_rejected_when_noise_multiplier_violates_global_policy(self):
        main.ENFORCE_PRIVACY_BUDGET = True
        main.SIMULATE_LOW_RESOURCES = False
        main.DP_NOISE_MULTIPLIER = 0.5

        budget_payload = {
            "epsilon": 10.0,
            "delta": 1e-5,
            "total_spent_epsilon": 1.0,
            "total_spent_delta": 0.0,
        }
        global_policy_payload = {
            "min_noise_multiplier": 0.0,
            "max_noise_multiplier": 0.1,
            "require_encrypted_updates": True,
        }
        client = FakeAsyncClient(
            get_responses={
                f"{main.POLICY_MANAGER_URL}/policies/budget/agent-1": FakeGetResponse(budget_payload),
                f"{main.POLICY_MANAGER_URL}/policies/global": FakeGetResponse(global_policy_payload),
            }
        )

        with patch.object(main.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(main.HTTPException) as exc:
                await main.start_local_round(round_id="r1", agent_id="agent-1")

        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail, "Participation rejected: Configured noise multiplier violates global policy")

    async def test_start_round_rejected_due_to_low_resources(self):
        main.ENFORCE_PRIVACY_BUDGET = False
        main.SIMULATE_LOW_RESOURCES = True
        main.SIMULATE_CPU_LOAD = 95
        main.SIMULATE_BATTERY_LEVEL = 80
        
        with self.assertRaises(main.HTTPException) as exc:
            await main.start_local_round(round_id="r1", agent_id="agent-1")
            
        self.assertEqual(exc.exception.status_code, 403)
        self.assertIn("Node resources exhausted", exc.exception.detail)


if __name__ == "__main__":
    unittest.main()
