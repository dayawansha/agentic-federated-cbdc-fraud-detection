import logging
import os
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel
import sys

# Add project root to sys.path to allow importing shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from shared.schemas.models import PrivacyBudget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Policy Manager Service")

# In-memory storage for demonstration (to be replaced by PostgreSQL)
agent_budgets: Dict[str, PrivacyBudget] = {}

class BudgetUpdateRequest(BaseModel):
    agent_id: str
    epsilon_spent: float
    delta_spent: float

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/policies/budget/{agent_id}", response_model=PrivacyBudget)
async def get_agent_budget(agent_id: str):
    if agent_id not in agent_budgets:
        # Initialize default budget if not exists
        agent_budgets[agent_id] = PrivacyBudget(epsilon=10.0, delta=1e-5)
    return agent_budgets[agent_id]

@app.post("/policies/budget/update")
async def update_budget(request: BudgetUpdateRequest):
    if request.agent_id not in agent_budgets:
        agent_budgets[request.agent_id] = PrivacyBudget(epsilon=10.0, delta=1e-5)
    
    budget = agent_budgets[request.agent_id]
    
    # Check if update exceeds total budget
    if budget.total_spent_epsilon + request.epsilon_spent > budget.epsilon:
        raise HTTPException(status_code=403, detail="Privacy budget exceeded (epsilon)")
    
    budget.total_spent_epsilon += request.epsilon_spent
    budget.total_spent_delta += request.delta_spent
    
    logger.info(f"Updated budget for agent {request.agent_id}: ε_spent={budget.total_spent_epsilon}")
    return {"status": "success", "current_budget": budget}

@app.get("/policies/global")
async def get_global_policies():
    return {
        "min_agents_per_round": 3,
        "max_rounds": 50,
        "aggregation_strategy": "FedAvg",
        "allowed_asset_types": ["CBDC"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
