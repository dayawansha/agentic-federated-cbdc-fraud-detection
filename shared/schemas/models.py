from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class FraudClass(int, Enum):
    ILLICIT = 1
    LICIT = 2
    UNKNOWN = 3

class TransactionBase(BaseModel):
    txId: int
    time_step: int
    amount: float
    features: List[float]
    label: Optional[FraudClass] = None

class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    TRAINING = "training"
    EVALUATING = "evaluating"

class TrainingRound(BaseModel):
    round_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str # "scheduled", "active", "completed", "failed"
    participating_agents: List[str]
    global_metrics: Dict[str, float] = {}

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FraudAlert(BaseModel):
    alert_id: str
    txId: int
    timestamp: datetime
    severity: AlertSeverity
    confidence_score: float
    reason: str
    status: str = "open" # "open", "investigating", "resolved", "false_positive"

class PrivacyBudget(BaseModel):
    epsilon: float = Field(..., gt=0)
    delta: float = Field(..., ge=0, le=1)
    total_spent_epsilon: float = 0.0
    total_spent_delta: float = 0.0

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

