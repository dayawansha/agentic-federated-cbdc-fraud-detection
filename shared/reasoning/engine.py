import logging
from typing import Any, Dict, List, Set

from shared.reasoning.inference_rules import (
    REASONING_ENGINE_ID,
    infer_aggregation_strategy,
    infer_coordinator_round,
    infer_local_training_plan,
    infer_participation,
)
from shared.reasoning.memory import get_agent_memory
from shared.reasoning.schemas import (
    AggregationStrategyDecision,
    CoordinatorRoundDecision,
    LocalTrainingPlanDecision,
    ParticipationDecisionReasoning,
)

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Autonomous reasoning engine for coordinator and bank-node agents.

    Uses a self-contained expert-inference pipeline (perception → memory → rules → action).
    No external LLM or third-party inference APIs.
    """

    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role
        self.memory = get_agent_memory(agent_id)

    @property
    def provider(self) -> str:
        return REASONING_ENGINE_ID

    async def reason_local_training_plan(self, context: Dict[str, Any]) -> LocalTrainingPlanDecision:
        plan = infer_local_training_plan(context, self.memory)
        decision = LocalTrainingPlanDecision.model_validate(plan)
        decision.provider = self.provider
        self.memory.remember(
            {
                "summary": (
                    f"Local plan: epochs={decision.local_epochs}, strategy={decision.local_training_strategy}, "
                    f"noise={decision.noise_multiplier}"
                ),
                "decision": decision.model_dump(),
                "previous_metrics": context.get("previous_metrics", {}),
            },
            long_term=True,
        )
        return decision

    async def reason_participation(self, context: Dict[str, Any]) -> ParticipationDecisionReasoning:
        participate, steps, rationale, confidence = infer_participation(context, self.memory)
        decision = ParticipationDecisionReasoning(
            participate=participate,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=rationale,
        )
        self.memory.remember(
            {"summary": f"Participation decision: participate={decision.participate}", "decision": decision.model_dump()},
            long_term=True,
        )
        return decision

    async def reason_aggregation_strategy(
        self,
        valid_updates: List[Dict[str, Any]],
        policies: Dict[str, Any],
        current_strategy: str,
        supported_strategies: Set[str],
    ) -> AggregationStrategyDecision:
        strategy, steps, confidence = infer_aggregation_strategy(
            valid_updates,
            policies,
            current_strategy,
            supported_strategies,
            self.memory,
        )
        decision = AggregationStrategyDecision(
            aggregation_strategy=strategy,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=f"Autonomous coordinator selected {strategy} for aggregation.",
        )
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
        selected, hint, escalate, steps, confidence = infer_coordinator_round(
            candidate_agents,
            policies,
            agent_profiles,
            self.memory,
        )
        decision = CoordinatorRoundDecision(
            selected_agent_ids=selected,
            aggregation_strategy_hint=hint,
            escalate_anomaly_review=escalate,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=f"Coordinator autonomously selected {len(selected)} participating agent(s).",
        )
        self.memory.remember(
            {"summary": decision.rationale_summary, "decision": decision.model_dump()},
            long_term=True,
        )
        return decision


_ENGINES: Dict[str, ReasoningEngine] = {}


def get_reasoning_engine(agent_id: str, role: str) -> ReasoningEngine:
    key = f"{role}:{agent_id}"
    if key not in _ENGINES:
        _ENGINES[key] = ReasoningEngine(agent_id, role)
    return _ENGINES[key]
