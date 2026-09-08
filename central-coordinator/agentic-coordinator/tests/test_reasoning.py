import sys
import unittest
from pathlib import Path

SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

from reasoning.inference_rules import REASONING_ENGINE_ID
from reasoning.engine import get_reasoning_engine
from reasoning.memory import reset_agent_memory


class TestCoordinatorReasoning(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_agent_memory()

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


if __name__ == "__main__":
    unittest.main()
