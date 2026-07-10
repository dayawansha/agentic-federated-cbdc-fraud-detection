import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.reasoning.inference_rules import REASONING_ENGINE_ID
from shared.reasoning.engine import get_reasoning_engine
from shared.reasoning.memory import reset_agent_memory


class TestReasoningEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_agent_memory()

    async def test_local_training_plan_produces_expert_inference(self):
        engine = get_reasoning_engine("bank-a", "local_agent")
        decision = await engine.reason_local_training_plan(
            {
                "rl_enabled": False,
                "selected_strategy": "FedAvg",
                "global_model_loaded": True,
                "participation_checks": {
                    "privacy_budget": {"epsilon": 10.0, "remaining_epsilon": 1.5, "required_reserve_epsilon": 0.5},
                    "policy_constraints": {"min_noise_multiplier": 0.0, "max_noise_multiplier": 0.2},
                },
                "previous_metrics": {"accuracy": 0.55, "loss": 0.9, "labeled_ratio": 0.2, "sparse_label_mode": 1.0},
                "inference_summary": {"high_risk_count": 3.0, "top_confidence": 0.92},
                "dp_noise_multiplier": 0.01,
                "default_local_training_epochs": 1,
                "max_adaptive_local_epochs": 3,
                "fedprox_mu": 1.0,
                "pseudo_label_weight_default": 0.35,
                "pseudo_label_confidence_default": 0.9,
                "alert_publish_limit": 5,
                "auto_alert_on_round_complete": True,
            }
        )

        self.assertEqual(decision.provider, REASONING_ENGINE_ID)
        self.assertGreaterEqual(decision.local_epochs, 2)
        self.assertEqual(decision.local_training_strategy, "FedProxGNN")
        self.assertGreater(decision.pseudo_label_weight, 0.0)
        self.assertTrue(decision.run_post_round_inference)
        self.assertGreater(len(decision.reasoning_steps), 0)

    async def test_participation_reasoning_approves_when_hard_constraints_pass(self):
        engine = get_reasoning_engine("bank-a", "local_agent")
        decision = await engine.reason_participation(
            {"hard_constraints_passed": True, "checks": {}, "last_metrics": {"accuracy": 0.9}}
        )
        self.assertTrue(decision.participate)
        self.assertEqual(decision.provider, REASONING_ENGINE_ID)

    async def test_participation_reasoning_rejects_critically_low_prior_accuracy(self):
        engine = get_reasoning_engine("bank-a", "local_agent")
        decision = await engine.reason_participation(
            {"hard_constraints_passed": True, "checks": {}, "last_metrics": {"accuracy": 0.4}}
        )
        self.assertFalse(decision.participate)

    async def test_aggregation_strategy_reasoning_switches_on_low_accuracy(self):
        engine = get_reasoning_engine("coordinator", "coordinator")
        decision = await engine.reason_aggregation_strategy(
            [{"agent_id": "a", "sample_size": 10, "metrics": {"accuracy": 0.55}}],
            {"fallback_aggregation_strategy": "WeightedFedAvg", "low_performance_accuracy": 0.8, "adaptive_rejected_update_ratio": 0.25},
            "FedAvg",
            {"FedAvg", "WeightedFedAvg", "AdaptiveFedAvg"},
        )
        self.assertEqual(decision.aggregation_strategy, "WeightedFedAvg")
        self.assertEqual(decision.provider, REASONING_ENGINE_ID)

    async def test_coordinator_round_reasoning_filters_low_reliability_agents(self):
        engine = get_reasoning_engine("coordinator", "coordinator")
        decision = await engine.reason_coordinator_round(
            ["http://agent-a", "http://agent-b"],
            {"minimum_agent_reliability_score": 0.5, "low_performance_accuracy": 0.8, "aggregation_strategy": "FedAvg"},
            {
                "http://agent-a": {"reliability_score": 0.9, "last_accuracy": 0.85},
                "http://agent-b": {"reliability_score": 0.2, "last_accuracy": 0.85},
            },
        )
        self.assertEqual(decision.selected_agent_ids, ["http://agent-a"])
        self.assertTrue(decision.escalate_anomaly_review)

    async def test_reinforcement_learning_tuning(self):
        engine = get_reasoning_engine("bank-a", "local_agent")
        # Initialize memory with a prior action state
        engine.memory.last_rl_state = "perf:H|sparse:L|budget:L"
        engine.memory.last_rl_action = 1
        engine.memory.last_rl_metrics = {"accuracy": 0.5}

        # Run reasoning which triggers Q-value update based on accuracy improvement (0.5 -> 0.8)
        decision = await engine.reason_local_training_plan(
            {
                "selected_strategy": "FedAvg",
                "global_model_loaded": True,
                "participation_checks": {
                    "privacy_budget": {"epsilon": 10.0, "remaining_epsilon": 1.5, "required_reserve_epsilon": 0.5},
                    "policy_constraints": {"min_noise_multiplier": 0.0, "max_noise_multiplier": 0.2},
                },
                "previous_metrics": {"accuracy": 0.8, "loss": 0.4, "labeled_ratio": 1.0, "sparse_label_mode": 0.0},
                "inference_summary": {"high_risk_count": 0.0, "top_confidence": 0.5},
                "dp_noise_multiplier": 0.01,
                "default_local_training_epochs": 1,
                "max_adaptive_local_epochs": 3,
                "fedprox_mu": 1.0,
                "pseudo_label_weight_default": 0.35,
                "pseudo_label_confidence_default": 0.9,
                "alert_publish_limit": 5,
                "auto_alert_on_round_complete": True,
            }
        )
        
        # Verify RL action selection worked and step was recorded
        rl_trace_steps = [s for s in decision.reasoning_steps if "RL Action:" in s]
        self.assertEqual(len(rl_trace_steps), 1)
        self.assertEqual(engine.memory.last_rl_metrics["accuracy"], 0.8)
        
        # Verify Q-table has updated values
        q_table = getattr(engine.memory, "rl_q_table", {})
        self.assertIn("perf:H|sparse:L|budget:L", q_table)


if __name__ == "__main__":
    unittest.main()
