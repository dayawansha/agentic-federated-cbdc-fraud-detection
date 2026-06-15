import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SRC = SERVICE_ROOT / "src"

if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

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


class TestAgenticCoordinator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main.round_updates.clear()
        main.round_expected_agents.clear()
        main.round_events.clear()
        main.agent_profiles.clear()

    async def test_submit_update_marks_round_complete_when_expected_agents_arrive(self):
        round_id = "round-1"
        main.round_expected_agents[round_id] = ["agent-a", "agent-b"]
        main.round_events[round_id] = asyncio.Event()

        first = main.UpdateSubmission(
            agent_id="agent-a",
            round_id=round_id,
            weights="dGVzdA==",
            encrypted_weights="Y2lwaGVy",
            encrypted_mask_share="bWFzay1h",
            sample_size=10,
            metrics={"loss": 0.4},
            privacy_applied=True,
            encryption_applied=True,
        )
        second = main.UpdateSubmission(
            agent_id="agent-b",
            round_id=round_id,
            weights="dGVzdDI=",
            encrypted_weights="Y2lwaGVyMg==",
            encrypted_mask_share="bWFzay1i",
            sample_size=12,
            metrics={"loss": 0.3},
            privacy_applied=True,
            encryption_applied=True,
        )

        with patch.object(main, "_store_secure_aggregation_mask", new=AsyncMock()) as store_mask_mock:
            first_ack = await main.submit_update(first)
            second_ack = await main.submit_update(second)

        self.assertEqual(first_ack.message, "Update received")
        self.assertEqual(second_ack.message, "Update received (round complete)")
        self.assertTrue(main.round_events[round_id].is_set())
        self.assertEqual(len(main.round_updates[round_id]), 2)
        self.assertEqual(store_mask_mock.await_count, 2)

    async def test_aggregate_results_without_updates_skips_aggregation(self):
        state = {
            "round_id": "round-empty",
            "active_agents": [],
            "updates_received": [],
            "valid_updates": [],
            "rejected_updates": [],
            "aggregation_complete": True,
            "metrics": {"existing": 1.0},
            "policies": {},
            "selected_strategy": "FedAvg",
            "current_step": "waiting_for_updates",
        }

        result = await main.aggregate_results(state)

        self.assertFalse(result["aggregation_complete"])
        self.assertEqual(result["current_step"], "round_complete")
        self.assertEqual(result["metrics"], {"existing": 1.0})

    async def test_select_agents_uses_configured_agent_urls(self):
        state = {
            "round_id": "round-select",
            "active_agents": [],
            "updates_received": [],
            "valid_updates": [],
            "rejected_updates": [],
            "aggregation_complete": False,
            "metrics": {},
            "policies": main._normalize_global_policies(None),
            "selected_strategy": "FedAvg",
            "current_step": "init",
        }

        result = await main.select_agents(state)

        self.assertEqual(result["active_agents"], main.LOCAL_AGENT_URLS)
        self.assertEqual(result["current_step"], "training_triggered")

    async def test_submit_update_rejects_unprotected_payload(self):
        update = main.UpdateSubmission(
            agent_id="agent-a",
            round_id="round-unsafe",
            weights="dGVzdA==",
            sample_size=10,
            metrics={"loss": 0.4},
            privacy_applied=False,
        )

        with self.assertRaises(main.HTTPException) as exc:
            await main.submit_update(update)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Protected model update required before submission")

    async def test_submit_update_rejects_missing_encrypted_metadata_when_declared(self):
        update = main.UpdateSubmission(
            agent_id="agent-a",
            round_id="round-incomplete",
            weights="dGVzdA==",
            sample_size=10,
            metrics={"loss": 0.4},
            privacy_applied=True,
            encryption_applied=True,
        )

        with self.assertRaises(main.HTTPException) as exc:
            await main.submit_update(update)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Encrypted payload metadata is required when encryption is declared")

    async def test_submit_update_rejects_missing_mask_share_when_encryption_declared(self):
        update = main.UpdateSubmission(
            agent_id="agent-a",
            round_id="round-mask-missing",
            weights="dGVzdA==",
            encrypted_weights="Y2lwaGVy",
            sample_size=10,
            metrics={"loss": 0.4},
            privacy_applied=True,
            encryption_applied=True,
        )

        with self.assertRaises(main.HTTPException) as exc:
            await main.submit_update(update)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Secure aggregation mask share is required when encryption is declared")

    async def test_submit_update_rejects_payload_commitment_mismatch(self):
        payload = "dGVzdA=="
        update = main.UpdateSubmission(
            agent_id="agent-a",
            round_id="round-hash",
            weights=payload,
            encrypted_weights="Y2lwaGVy",
            encrypted_mask_share="bWFzay1h",
            protected_payload_sha256="0" * 64,
            encrypted_payload_sha256=hashlib.sha256("Y2lwaGVy".encode("ascii")).hexdigest(),
            sample_size=10,
            metrics={"loss": 0.4},
            privacy_applied=True,
            encryption_applied=True,
        )

        with self.assertRaises(main.HTTPException) as exc:
            await main.submit_update(update)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Protected payload commitment mismatch")

    async def test_validate_updates_rejects_low_quality_payloads(self):
        policies = main._normalize_global_policies(
            {
                "min_update_sample_size": 5,
                "min_update_accuracy": 0.7,
                "required_metrics": ["accuracy", "f1_score"],
                "max_update_loss": 1.0,
                "require_encrypted_updates": False,
            }
        )
        updates = [
            main.UpdateSubmission(
                agent_id="good-agent",
                round_id="round-quality",
                weights="dGVzdA==",
                sample_size=8,
                metrics={"accuracy": 0.9, "f1_score": 0.88, "loss": 0.2},
                privacy_applied=True,
            ),
            main.UpdateSubmission(
                agent_id="low-acc-agent",
                round_id="round-quality",
                weights="dGVzdA==",
                sample_size=8,
                metrics={"accuracy": 0.4, "f1_score": 0.5, "loss": 0.3},
                privacy_applied=True,
            ),
            main.UpdateSubmission(
                agent_id="small-agent",
                round_id="round-quality",
                weights="dGVzdA==",
                sample_size=1,
                metrics={"accuracy": 0.95, "f1_score": 0.92, "loss": 0.1},
                privacy_applied=True,
            ),
        ]

        valid_updates, rejected_updates = main._validate_updates(updates, policies)

        self.assertEqual([update.agent_id for update in valid_updates], ["good-agent"])
        self.assertEqual(len(rejected_updates), 2)
        self.assertEqual(rejected_updates[0]["reason"], "accuracy_below_policy")
        self.assertEqual(rejected_updates[1]["reason"], "sample_size_below_policy")

    async def test_validate_updates_requires_encrypted_updates_when_policy_enabled(self):
        policies = main._normalize_global_policies({"require_encrypted_updates": True})
        updates = [
            main.UpdateSubmission(
                agent_id="agent-a",
                round_id="round-encrypted-required",
                weights="dGVzdA==",
                sample_size=8,
                metrics={"accuracy": 0.9, "f1_score": 0.88, "loss": 0.2},
                privacy_applied=True,
                encryption_applied=False,
            )
        ]

        valid_updates, rejected_updates = main._validate_updates(updates, policies)

        self.assertEqual(valid_updates, [])
        self.assertEqual(rejected_updates[0]["reason"], "encrypted_update_required")

    async def test_aggregate_results_skips_round_when_valid_updates_below_policy_minimum(self):
        state = {
            "round_id": "round-policy-gated",
            "active_agents": [],
            "updates_received": [
                main.UpdateSubmission(
                    agent_id="agent-a",
                    round_id="round-policy-gated",
                    weights="dGVzdA==",
                    sample_size=10,
                    metrics={"accuracy": 0.92, "f1_score": 0.89, "loss": 0.2},
                    privacy_applied=True,
                ),
            ],
            "valid_updates": [],
            "rejected_updates": [],
            "aggregation_complete": False,
            "metrics": {},
            "policies": main._normalize_global_policies({"min_agents_per_round": 2, "require_encrypted_updates": False}),
            "selected_strategy": "FedAvg",
            "current_step": "aggregating",
        }

        result = await main.aggregate_results(state)

        self.assertFalse(result["aggregation_complete"])
        self.assertEqual(result["metrics"]["accepted_updates"], 1.0)
        self.assertEqual(result["metrics"]["rejected_updates"], 0.0)
        self.assertEqual(result["current_step"], "round_complete")

    async def test_validate_updates_rejects_suspicious_metric_ranges_and_timestamps(self):
        stale_timestamp = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        policies = main._normalize_global_policies(
            {
                "min_noise_multiplier": 0.01,
                "max_noise_multiplier": 0.2,
                "require_encrypted_updates": False,
            }
        )
        updates = [
            main.UpdateSubmission(
                agent_id="bad-metric-agent",
                round_id="round-suspicious",
                weights="dGVzdA==",
                sample_size=8,
                metrics={"accuracy": 1.2, "f1_score": 0.9, "loss": 0.1},
                privacy_applied=True,
                noise_multiplier=0.05,
            ),
            main.UpdateSubmission(
                agent_id="bad-noise-agent",
                round_id="round-suspicious",
                weights="dGVzdA==",
                sample_size=8,
                metrics={"accuracy": 0.9, "f1_score": 0.88, "loss": 0.1},
                privacy_applied=True,
                noise_multiplier=0.5,
            ),
            main.UpdateSubmission(
                agent_id="stale-agent",
                round_id="round-suspicious",
                weights="dGVzdA==",
                sample_size=8,
                metrics={"accuracy": 0.9, "f1_score": 0.88, "loss": 0.1},
                privacy_applied=True,
                noise_multiplier=0.05,
                client_timestamp=stale_timestamp,
            ),
        ]

        valid_updates, rejected_updates = main._validate_updates(updates, policies)

        self.assertEqual(valid_updates, [])
        self.assertEqual(
            [rejection["reason"] for rejection in rejected_updates],
            ["accuracy_out_of_range", "noise_multiplier_out_of_range", "stale_client_timestamp"],
        )

    async def test_validate_updates_rejects_peer_outliers(self):
        policies = main._normalize_global_policies(
            {
                "min_update_accuracy": 0.0,
                "max_accuracy_peer_delta": 0.2,
                "max_loss_peer_delta": 0.4,
                "require_encrypted_updates": False,
            }
        )
        updates = [
            main.UpdateSubmission(
                agent_id="agent-a",
                round_id="round-outlier",
                weights="dGVzdA==",
                sample_size=10,
                metrics={"accuracy": 0.88, "f1_score": 0.86, "loss": 0.25},
                privacy_applied=True,
            ),
            main.UpdateSubmission(
                agent_id="agent-b",
                round_id="round-outlier",
                weights="dGVzdA==",
                sample_size=10,
                metrics={"accuracy": 0.87, "f1_score": 0.85, "loss": 0.28},
                privacy_applied=True,
            ),
            main.UpdateSubmission(
                agent_id="agent-c",
                round_id="round-outlier",
                weights="dGVzdA==",
                sample_size=10,
                metrics={"accuracy": 0.2, "f1_score": 0.19, "loss": 2.0},
                privacy_applied=True,
            ),
        ]

        valid_updates, rejected_updates = main._validate_updates(updates, policies)

        self.assertEqual([update.agent_id for update in valid_updates], ["agent-a", "agent-b"])
        self.assertEqual(len(rejected_updates), 1)
        self.assertEqual(rejected_updates[0]["agent_id"], "agent-c")
        self.assertEqual(rejected_updates[0]["reason"], "peer_accuracy_outlier")

    async def test_validate_updates_requires_secure_aggregation_mask_when_encryption_is_required(self):
        policies = main._normalize_global_policies({"require_encrypted_updates": True})
        updates = [
            main.UpdateSubmission(
                agent_id="agent-a",
                round_id="round-mask-required",
                weights="dGVzdA==",
                encrypted_weights="ZW5jcnlwdGVk",
                sample_size=8,
                metrics={"accuracy": 0.9, "f1_score": 0.88, "loss": 0.2},
                privacy_applied=True,
                encryption_applied=True,
            )
        ]

        valid_updates, rejected_updates = main._validate_updates(updates, policies)

        self.assertEqual(valid_updates, [])
        self.assertEqual(rejected_updates[0]["reason"], "secure_aggregation_mask_required")

    async def test_select_agents_filters_on_governance_and_reliability(self):
        main.agent_profiles["http://agent-a"] = {"accepted_updates": 1.0, "rejected_updates": 0.0, "reliability_score": 0.9, "last_accuracy": 0.9}
        main.agent_profiles["http://agent-b"] = {"accepted_updates": 0.0, "rejected_updates": 3.0, "reliability_score": 0.0, "last_accuracy": 0.0}
        state = {
            "round_id": "round-select-governed",
            "active_agents": [],
            "updates_received": [],
            "valid_updates": [],
            "rejected_updates": [],
            "aggregation_complete": False,
            "metrics": {},
            "policies": main._normalize_global_policies({"minimum_agent_reliability_score": 0.5}),
            "selected_strategy": "FedAvg",
            "current_step": "init",
        }

        async def fake_get_governance_agent(_client, agent_id):
            return {
                "agent_id": agent_id,
                "active": True,
                "allowed_asset_types": ["CBDC"],
                "minimum_reliability_score": 0.0,
            }

        with patch.object(main, "LOCAL_AGENT_URLS", ["http://agent-a", "http://agent-b"]):
            with patch.object(main, "_get_governance_agent", new=AsyncMock(side_effect=fake_get_governance_agent)):
                result = await main.select_agents(state)

        self.assertEqual(result["active_agents"], ["http://agent-a"])

    async def test_select_aggregation_strategy_can_switch_to_weighted_fedavg(self):
        updates = [
            main.UpdateSubmission(
                agent_id="agent-a",
                round_id="round-adapt",
                weights="dGVzdA==",
                encrypted_weights="Y2lwaGVy",
                sample_size=10,
                metrics={"accuracy": 0.55, "f1_score": 0.54, "loss": 0.3},
                privacy_applied=True,
                encryption_applied=True,
            )
        ]
        strategy = main._select_aggregation_strategy(
            updates,
            main._normalize_global_policies({"fallback_aggregation_strategy": "WeightedFedAvg", "low_performance_accuracy": 0.8}),
            "FedAvg",
        )

        self.assertEqual(strategy, "WeightedFedAvg")


if __name__ == "__main__":
    unittest.main()
