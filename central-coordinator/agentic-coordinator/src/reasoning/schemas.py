from typing import List
from pydantic import BaseModel, Field


class ReasoningDecisionBase(BaseModel):
    reasoning_steps: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    provider: str = "expert-inference"


class AggregationStrategyDecision(ReasoningDecisionBase):
    aggregation_strategy: str = "FedAvg"
    rationale_summary: str = ""


class CoordinatorRoundDecision(ReasoningDecisionBase):
    selected_agent_ids: List[str] = Field(default_factory=list)
    aggregation_strategy_hint: str = "FedAvg"
    escalate_anomaly_review: bool = False
    rationale_summary: str = ""
