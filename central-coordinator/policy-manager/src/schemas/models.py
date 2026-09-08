from pydantic import BaseModel, Field


class PrivacyBudget(BaseModel):
    epsilon: float = Field(..., gt=0)
    delta: float = Field(..., ge=0, le=1)
    total_spent_epsilon: float = 0.0
    total_spent_delta: float = 0.0
