from typing import List
from pydantic import BaseModel, Field


class ReasoningDecisionBase(BaseModel):
    reasoning_steps: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    provider: str = "expert-inference"


class LocalTrainingPlanDecision(ReasoningDecisionBase):
    local_epochs: int = Field(ge=1, le=10)
    noise_multiplier: float = Field(ge=0.0, le=5.0)
    local_training_strategy: str = "FedAvg"
    fedprox_mu: float = Field(default=1.0, ge=0.0, le=10.0)
    pseudo_label_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    pseudo_label_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    run_post_round_inference: bool = True
    post_round_inference_limit: int = Field(default=5, ge=1, le=50)
    risk_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    performance_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    sparse_label_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    plan_confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class ParticipationDecisionReasoning(ReasoningDecisionBase):
    participate: bool = True
    rationale_summary: str = ""
