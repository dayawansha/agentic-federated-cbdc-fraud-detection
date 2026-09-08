from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class WeightNegotiationItem(BaseModel):
    agent_id: str
    sample_size: int
    reliability_score: float
    metrics: Dict[str, float] = {}


class WeightNegotiationRequest(BaseModel):
    round_id: str
    agents: List[WeightNegotiationItem]


class WeightNegotiationResponse(BaseModel):
    agent_id: str
    proposed_weights: Dict[str, float]


class FraudPatternProposal(BaseModel):
    proposal_id: str
    proposer_id: str
    pattern_name: str
    feature_indicators: Dict[str, float]
    rationale: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConsensusVote(BaseModel):
    agent_id: str
    proposal_id: str
    vote: str
    reason: Optional[str] = None
