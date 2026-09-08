# Import Python's built-in logging module (used to write logs/status messages during execution)
import logging
# Import type-hinting annotations (tells developers the expected types of dictionary keys, values, etc.)
from typing import Any, Dict, List, Set

# Import the inference functions from our rules file.
# The 'reasoning/inference_rules.py' file contains the hard rules that make decisions.
from reasoning.inference_rules import (
    REASONING_ENGINE_ID,
    infer_aggregation_strategy,
    infer_coordinator_round,
)
# Import memory managers to get or store agent history
from reasoning.memory import get_agent_memory
# Import schemas (Pydantic classes that validate structure/data types of our outputs)
from reasoning.schemas import (
    AggregationStrategyDecision,
    CoordinatorRoundDecision,
)

# Set up a logger specifically for this file's namespace
logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Autonomous reasoning engine for the central coordinator.

    Uses a self-contained expert-inference pipeline (perception → memory → rules → action).
    No external LLM or third-party inference APIs are used.

    For non-Python readers:
    - This class acts as the "brain" for the central manager (coordinator).
    - It decides:
      1) How the coordinator aggregates models.
      2) Which agents the coordinator selects for a round.
    """

    def __init__(self, agent_id: str, role: str):
        # 'self.agent_id' holds the name/id of this reasoning instance (e.g. "agentic-coordinator")
        self.agent_id = agent_id
        # 'self.role' holds the role (e.g. "coordinator")
        self.role = role
        # Retrieve the memory object associated with this agent from memory storage
        self.memory = get_agent_memory(agent_id)

    @property
    def provider(self) -> str:
        # A 'property' is a special Python method that can be accessed like a variable (without parentheses)
        return REASONING_ENGINE_ID

    async def reason_aggregation_strategy(
        self,
        valid_updates: List[Dict[str, Any]],
        policies: Dict[str, Any],
        current_strategy: str,
        supported_strategies: Set[str],
    ) -> AggregationStrategyDecision:
        """
        Decides which weight aggregation algorithm the coordinator should use (FedAvg, RobustMedian, etc.).
        """
        # Evaluate rules based on the reliability scores of reporting agents and policy requirements
        strategy, steps, confidence = infer_aggregation_strategy(
            valid_updates,
            policies,
            current_strategy,
            supported_strategies,
            self.memory,
        )
        # Construct output schema
        decision = AggregationStrategyDecision(
            aggregation_strategy=strategy,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=f"Autonomous coordinator selected {strategy} for aggregation.",
        )
        # Persist decision in memory
        self.memory.remember(
            {"summary": f"Aggregation strategy: {decision.aggregation_strategy}", "decision": decision.model_dump()},
            long_term=True,
        )
        return decision

    async def reason_coordinator_round(
        self,
        candidate_agents: List[str],
        policies: Dict[str, Any],
        agent_profiles: Dict[str, Dict[str, float]],
    ) -> CoordinatorRoundDecision:
        """
        Decides which bank nodes to invite to the current federated learning round.
        """
        # Evaluate compliance, reliability history, and online status to filter candidates
        selected, hint, escalate, steps, confidence = infer_coordinator_round(
            candidate_agents,
            policies,
            agent_profiles,
            self.memory,
        )
        # Construct output schema
        decision = CoordinatorRoundDecision(
            selected_agent_ids=selected,
            aggregation_strategy_hint=hint,
            escalate_anomaly_review=escalate,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=f"Coordinator autonomously selected {len(selected)} participating agent(s).",
        )
        # Persist in memory
        self.memory.remember(
            {"summary": decision.rationale_summary, "decision": decision.model_dump()},
            long_term=True,
        )
        return decision


# Create a dictionary to cache ReasoningEngine instances so we don't recreate them on every call
_ENGINES: Dict[str, ReasoningEngine] = {}


def get_reasoning_engine(agent_id: str, role: str) -> ReasoningEngine:
    """
    Helper function to get or create a ReasoningEngine for a specific agent/role combination.
    """
    key = f"{role}:{agent_id}"
    if key not in _ENGINES:
        _ENGINES[key] = ReasoningEngine(agent_id, role)
    return _ENGINES[key]
