import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Ensure `/app` is on the import path inside the container so `shared` can be imported.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.schemas.models import PrivacyBudget
from sqlalchemy import Column, DateTime, Float, String, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Policy Manager Service")

def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    database = os.getenv("POSTGRES_DB", "federated_fraud_db")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

DATABASE_URL = _build_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class AgentBudget(Base):
    __tablename__ = "agent_budgets"

    agent_id = Column(String, primary_key=True)
    epsilon = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    total_spent_epsilon = Column(Float, nullable=False, default=0.0)
    total_spent_delta = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class BudgetUpdateRequest(BaseModel):
    agent_id: str
    epsilon_spent: float
    delta_spent: float

class BudgetSetRequest(BaseModel):
    agent_id: str
    epsilon: float
    delta: float

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)

def _get_or_create_budget(agent_id: str, default_epsilon: float = 10.0, default_delta: float = 1e-5) -> AgentBudget:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        existing = session.get(AgentBudget, agent_id)
        if existing:
            return existing
        budget = AgentBudget(
            agent_id=agent_id,
            epsilon=default_epsilon,
            delta=default_delta,
            total_spent_epsilon=0.0,
            total_spent_delta=0.0,
            updated_at=now,
        )
        session.add(budget)
        session.commit()
        session.refresh(budget)
        return budget

def _to_privacy_budget(row: AgentBudget) -> PrivacyBudget:
    return PrivacyBudget(
        epsilon=float(row.epsilon),
        delta=float(row.delta),
        total_spent_epsilon=float(row.total_spent_epsilon),
        total_spent_delta=float(row.total_spent_delta),
    )

@app.get("/policies/budget/{agent_id}", response_model=PrivacyBudget)
async def get_agent_budget(agent_id: str):
    budget = _get_or_create_budget(agent_id)
    return _to_privacy_budget(budget)

@app.post("/policies/budget/update")
async def update_budget(request: BudgetUpdateRequest):
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        budget = session.get(AgentBudget, request.agent_id)
        if budget is None:
            budget = AgentBudget(
                agent_id=request.agent_id,
                epsilon=10.0,
                delta=1e-5,
                total_spent_epsilon=0.0,
                total_spent_delta=0.0,
                updated_at=now,
            )
            session.add(budget)
            session.flush()

        if float(budget.total_spent_epsilon) + float(request.epsilon_spent) > float(budget.epsilon):
            raise HTTPException(status_code=403, detail="Privacy budget exceeded (epsilon)")

        budget.total_spent_epsilon = float(budget.total_spent_epsilon) + float(request.epsilon_spent)
        budget.total_spent_delta = float(budget.total_spent_delta) + float(request.delta_spent)
        budget.updated_at = now
        session.commit()
        session.refresh(budget)

    logger.info(f"Updated budget for agent {request.agent_id}: ε_spent={budget.total_spent_epsilon}")
    return {"status": "success", "current_budget": _to_privacy_budget(budget)}

@app.post("/policies/budget/set")
async def set_budget(request: BudgetSetRequest):
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        budget = session.get(AgentBudget, request.agent_id)
        if budget is None:
            budget = AgentBudget(
                agent_id=request.agent_id,
                epsilon=float(request.epsilon),
                delta=float(request.delta),
                total_spent_epsilon=0.0,
                total_spent_delta=0.0,
                updated_at=now,
            )
            session.add(budget)
        else:
            budget.epsilon = float(request.epsilon)
            budget.delta = float(request.delta)
            budget.updated_at = now
        session.commit()
        session.refresh(budget)
        return {"status": "success", "current_budget": _to_privacy_budget(budget)}

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
