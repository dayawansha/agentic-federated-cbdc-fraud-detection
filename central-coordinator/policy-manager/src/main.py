"""
================================================================================
POLICY MANAGER - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Policy Manager as the "Compliance Officer" and "Gatekeeper" of the system.
It enforces rules of cooperation and protects privacy budgets across all banks.

Its main responsibilities include:
1. PRIVACY BUDGET GATING: Every time a bank node participates in a training round,
   it leaks a minute amount of mathematical privacy. We represent this leakage allowance
   with "Epsilon" (strength of privacy) and "Delta" (probability of information leak).
   The Policy Manager records this usage like a debit card. If a bank's privacy card
   has insufficient funds, they are barred from participating to prevent any data leak.
2. GOVERNANCE AND ELIGIBILITY: It keeps a registry of which bank nodes are allowed to
   participate in federated rounds and what global thresholds (e.g., minimum local
   accuracy, maximum local loss) they must satisfy.
3. CRYPTOGRAPHIC KEY ESCROW: In secure aggregation, models are masked with private keys.
   The Policy Manager acts as an escrow agent, storing encrypted shares of these masks
   so they can be reconstructed collectively during aggregation without exposing
   any single bank's raw model weights to the central coordinator.
================================================================================
"""
import logging
import os
import sys
import base64
import hashlib
import io
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Ensure `/app` is on the import path inside the container so `shared` can be imported.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.schemas.models import PrivacyBudget
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, create_engine, desc, select
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
DEFAULT_GLOBAL_POLICIES: Dict[str, Any] = {
    "min_agents_per_round": 1,
    "max_rounds": 50,
    "aggregation_strategy": "FedAvg",
    "fallback_aggregation_strategy": "AdaptiveFedAvg",
    "low_performance_accuracy": 0.8,
    "min_update_sample_size": 1,
    "min_update_accuracy": 0.5,
    "max_update_loss": 2.5,
    "min_noise_multiplier": 0.0,
    "max_noise_multiplier": 1.0,
    "max_accuracy_peer_delta": 0.35,
    "max_loss_peer_delta": 1.5,
    "required_metrics": ["accuracy", "f1_score"],
    "allowed_asset_types": ["CBDC"],
    "require_encrypted_updates": True,
    "minimum_agent_reliability_score": 0.25,
    "adaptive_rejected_update_ratio": 0.25,
    "adaptive_strategy_on_rejection": "PerformanceWeightedFedAvg",
    "fedprox_mu": 1.0,
}

class AgentBudget(Base):
    __tablename__ = "agent_budgets"

    agent_id = Column(String, primary_key=True)
    epsilon = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    total_spent_epsilon = Column(Float, nullable=False, default=0.0)
    total_spent_delta = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class GlobalPolicyRow(Base):
    __tablename__ = "global_policies"

    policy_name = Column(String, primary_key=True)
    policy_version = Column(Integer, nullable=False, default=1)
    policy_payload = Column(JSON, nullable=False, default=dict)
    updated_by = Column(String, nullable=False, default="system")
    updated_at = Column(DateTime(timezone=True), nullable=False)

class GovernanceAgentRow(Base):
    __tablename__ = "governance_agents"

    agent_id = Column(String, primary_key=True)
    active = Column(Boolean, nullable=False, default=True)
    allowed_asset_types = Column(JSON, nullable=False, default=list)
    minimum_reliability_score = Column(Float, nullable=False, default=0.0)
    notes = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class GovernanceEventRow(Base):
    __tablename__ = "governance_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

class SecureAggregationMaskRow(Base):
    __tablename__ = "secure_aggregation_masks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=False)
    encrypted_mask_share = Column(String, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)

class BudgetUpdateRequest(BaseModel):
    agent_id: str
    epsilon_spent: float
    delta_spent: float

class BudgetSetRequest(BaseModel):
    agent_id: str
    epsilon: float
    delta: float

class GlobalPolicyUpdateRequest(BaseModel):
    policies: Dict[str, Any]
    updated_by: str = "system"

class GovernanceAgentRequest(BaseModel):
    agent_id: str
    active: bool = True
    allowed_asset_types: List[str] = ["CBDC"]
    minimum_reliability_score: float = 0.0
    notes: Optional[str] = None

class GovernanceAgentResponse(BaseModel):
    agent_id: str
    active: bool
    allowed_asset_types: List[str]
    minimum_reliability_score: float
    notes: Optional[str] = None
    updated_at: datetime

class GovernanceEventResponse(BaseModel):
    id: int
    agent_id: Optional[str] = None
    event_type: str
    details: Dict[str, Any]
    created_at: datetime

class SecureAggregationMaskSubmitRequest(BaseModel):
    round_id: str
    agent_id: str
    encrypted_mask_share: str

class SecureAggregationMaskAggregateItem(BaseModel):
    agent_id: str
    sample_size: int
    reliability_score: float = 1.0
    metrics: Dict[str, float] = {}

class SecureAggregationMaskAggregateRequest(BaseModel):
    round_id: str
    strategy: str = "FedAvg"
    updates: List[SecureAggregationMaskAggregateItem]

class SecureAggregationMaskAggregateResponse(BaseModel):
    aggregate_mask: str
    participant_count: int


class SecureAggregationEscrowPublicKeyResponse(BaseModel):
    scheme: str
    public_key: str

def _resolve_transport_cipher() -> Fernet:
    explicit_key = os.getenv("PRIVACY_FERNET_KEY")
    if explicit_key:
        return Fernet(explicit_key.encode("ascii"))

    seed = os.getenv("PRIVACY_KEY_SEED", "development-only-shared-key")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(derived_key)

TRANSPORT_CIPHER = _resolve_transport_cipher()


def _resolve_escrow_private_key() -> x25519.X25519PrivateKey:
    explicit_key = os.getenv("SECURE_AGGREGATION_ESCROW_PRIVATE_KEY_B64")
    if explicit_key:
        return x25519.X25519PrivateKey.from_private_bytes(base64.b64decode(explicit_key))

    seed = os.getenv("SECURE_AGGREGATION_ESCROW_SEED", "development-only-secure-aggregation-escrow")
    derived_private_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
    return x25519.X25519PrivateKey.from_private_bytes(derived_private_bytes)


ESCROW_PRIVATE_KEY = _resolve_escrow_private_key()
ESCROW_PUBLIC_KEY = ESCROW_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/secure-aggregation/escrow/public-key", response_model=SecureAggregationEscrowPublicKeyResponse)
async def get_secure_aggregation_escrow_public_key():
    return SecureAggregationEscrowPublicKeyResponse(
        scheme="x25519-hkdf-fernet-v1",
        public_key=base64.b64encode(ESCROW_PUBLIC_KEY).decode("ascii"),
    )

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

def _normalize_global_policies(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = dict(DEFAULT_GLOBAL_POLICIES)
    if payload:
        merged.update(dict(payload))
    merged["allowed_asset_types"] = [str(asset_type) for asset_type in (merged.get("allowed_asset_types") or ["CBDC"])]
    merged["required_metrics"] = [str(metric) for metric in (merged.get("required_metrics") or ["accuracy", "f1_score"])]
    merged["require_encrypted_updates"] = bool(merged.get("require_encrypted_updates", True))
    merged["minimum_agent_reliability_score"] = float(merged.get("minimum_agent_reliability_score", 0.25))
    merged["adaptive_rejected_update_ratio"] = float(merged.get("adaptive_rejected_update_ratio", 0.25))
    return merged

def _record_governance_event(event_type: str, details: Dict[str, Any], agent_id: Optional[str] = None) -> None:
    with SessionLocal() as session:
        session.add(
            GovernanceEventRow(
                agent_id=agent_id,
                event_type=event_type,
                details=details or {},
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

def _to_governance_agent_response(row: GovernanceAgentRow) -> GovernanceAgentResponse:
    return GovernanceAgentResponse(
        agent_id=row.agent_id,
        active=bool(row.active),
        allowed_asset_types=list(row.allowed_asset_types or []),
        minimum_reliability_score=float(row.minimum_reliability_score),
        notes=row.notes,
        updated_at=row.updated_at,
    )

def _to_privacy_budget(row: AgentBudget) -> PrivacyBudget:
    return PrivacyBudget(
        epsilon=float(row.epsilon),
        delta=float(row.delta),
        total_spent_epsilon=float(row.total_spent_epsilon),
        total_spent_delta=float(row.total_spent_delta),
    )

def _aggregation_weight(item: SecureAggregationMaskAggregateItem, strategy: str) -> float:
    base_weight = float(max(0, int(item.sample_size)))
    if strategy == "WeightedFedAvg":
        return base_weight * max(0.1, float(item.reliability_score))
    if strategy == "PerformanceWeightedFedAvg":
        return base_weight * _metric_quality_score(item.metrics or {})
    if strategy == "AdaptiveFedAvg":
        return base_weight * max(0.1, float(item.reliability_score)) * _metric_quality_score(item.metrics or {})
    return base_weight


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _metric_quality_score(metrics: Dict[str, float]) -> float:
    if not metrics:
        return 1.0

    components: List[float] = []
    for key in ("accuracy", "f1_score", "precision", "recall", "roc_auc", "auc"):
        if key in metrics:
            components.append(_clamp(float(metrics[key]), 0.0, 1.0))

    if "loss" in metrics:
        components.append(1.0 / (1.0 + max(0.0, float(metrics["loss"]))))

    if not components:
        return 1.0
    return max(0.1, sum(components) / len(components))

def _aggregate_mask_payloads(mask_payloads: List[bytes], aggregation_weights: List[float]) -> bytes:
    if not mask_payloads:
        raise HTTPException(status_code=400, detail="No secure aggregation masks provided")
    total_weight = float(sum(aggregation_weights))
    if total_weight <= 0:
        raise HTTPException(status_code=400, detail="Invalid secure aggregation mask weights")

    import torch

    base_state = torch.load(io.BytesIO(mask_payloads[0]))
    aggregate_state = {key: torch.zeros_like(value).float() for key, value in base_state.items()}
    for payload, weight in zip(mask_payloads, aggregation_weights):
        mask_state = torch.load(io.BytesIO(payload))
        normalized_weight = float(weight) / total_weight
        for key in aggregate_state:
            aggregate_state[key] += mask_state[key].float() * normalized_weight

    buffer = io.BytesIO()
    torch.save(aggregate_state, buffer)
    return buffer.getvalue()


def _decrypt_escrowed_mask_share(mask_share: str) -> bytes:
    try:
        package = json.loads(mask_share)
    except Exception:
        package = None

    if isinstance(package, dict) and package.get("scheme") == "x25519-hkdf-fernet-v1":
        round_id = str(package.get("round_id", ""))
        agent_id = str(package.get("agent_id", ""))
        ephemeral_public_key_b64 = str(package.get("ephemeral_public_key", ""))
        ciphertext_b64 = str(package.get("ciphertext", ""))
        mask_commitment = str(package.get("mask_commitment", ""))
        if not round_id or not agent_id or not ephemeral_public_key_b64 or not ciphertext_b64:
            raise HTTPException(status_code=400, detail="Incomplete secure aggregation escrow package")

        try:
            ephemeral_public_key = x25519.X25519PublicKey.from_public_bytes(base64.b64decode(ephemeral_public_key_b64))
            shared_secret = ESCROW_PRIVATE_KEY.exchange(ephemeral_public_key)
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=f"secure-aggregation:{round_id}:{agent_id}".encode("utf-8"),
            ).derive(shared_secret)
            cipher = Fernet(base64.urlsafe_b64encode(derived_key))
            mask_payload = cipher.decrypt(base64.b64decode(ciphertext_b64))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid secure aggregation escrow package for {agent_id}") from exc

        if mask_commitment and hashlib.sha256(mask_payload).hexdigest() != mask_commitment:
            raise HTTPException(status_code=400, detail=f"Secure aggregation escrow commitment mismatch for {agent_id}")
        return mask_payload

    try:
        encrypted_mask = base64.b64decode(mask_share)
        return TRANSPORT_CIPHER.decrypt(encrypted_mask)
    except InvalidToken as exc:
        raise HTTPException(status_code=400, detail="Invalid legacy secure aggregation mask payload") from exc

@app.get("/policies/budget/{agent_id:path}", response_model=PrivacyBudget)
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
    _record_governance_event(
        "privacy_budget_updated",
        {
            "epsilon_spent": float(request.epsilon_spent),
            "delta_spent": float(request.delta_spent),
            "total_spent_epsilon": float(budget.total_spent_epsilon),
            "total_spent_delta": float(budget.total_spent_delta),
        },
        agent_id=request.agent_id,
    )
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
        _record_governance_event(
            "privacy_budget_set",
            {"epsilon": float(request.epsilon), "delta": float(request.delta)},
            agent_id=request.agent_id,
        )
        return {"status": "success", "current_budget": _to_privacy_budget(budget)}

@app.get("/policies/global")
async def get_global_policies():
    with SessionLocal() as session:
        row = session.get(GlobalPolicyRow, "global")
        if row is None:
            return _normalize_global_policies(None)
        normalized = _normalize_global_policies(row.policy_payload or {})
        normalized["policy_version"] = int(row.policy_version)
        normalized["updated_by"] = row.updated_by
        normalized["updated_at"] = row.updated_at.isoformat()
        return normalized

@app.post("/policies/global")
async def update_global_policies(request: GlobalPolicyUpdateRequest):
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        row = session.get(GlobalPolicyRow, "global")
        if row is None:
            current_payload = dict(DEFAULT_GLOBAL_POLICIES)
            version = 1
            row = GlobalPolicyRow(
                policy_name="global",
                policy_version=version,
                policy_payload=current_payload,
                updated_by=request.updated_by,
                updated_at=now,
            )
            session.add(row)
            session.flush()
        merged = _normalize_global_policies({**(row.policy_payload or {}), **(request.policies or {})})
        row.policy_payload = merged
        row.policy_version = int(row.policy_version) + 1
        row.updated_by = request.updated_by
        row.updated_at = now
        session.commit()
        session.refresh(row)

    _record_governance_event(
        "global_policy_updated",
        {"updated_by": request.updated_by, "policy_version": int(row.policy_version), "policies": row.policy_payload or {}},
    )
    response = _normalize_global_policies(row.policy_payload or {})
    response["policy_version"] = int(row.policy_version)
    response["updated_by"] = row.updated_by
    response["updated_at"] = row.updated_at.isoformat()
    return response

@app.get("/governance/agent/{agent_id:path}", response_model=GovernanceAgentResponse)
async def get_governance_agent(agent_id: str):
    with SessionLocal() as session:
        row = session.get(GovernanceAgentRow, agent_id)
        if row is None:
            row = GovernanceAgentRow(
                agent_id=agent_id,
                active=True,
                allowed_asset_types=["CBDC"],
                minimum_reliability_score=0.0,
                notes=None,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        return _to_governance_agent_response(row)

@app.post("/governance/agent", response_model=GovernanceAgentResponse)
async def upsert_governance_agent(request: GovernanceAgentRequest):
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        row = session.get(GovernanceAgentRow, request.agent_id)
        if row is None:
            row = GovernanceAgentRow(
                agent_id=request.agent_id,
                active=bool(request.active),
                allowed_asset_types=list(request.allowed_asset_types or ["CBDC"]),
                minimum_reliability_score=float(request.minimum_reliability_score),
                notes=request.notes,
                updated_at=now,
            )
            session.add(row)
        else:
            row.active = bool(request.active)
            row.allowed_asset_types = list(request.allowed_asset_types or ["CBDC"])
            row.minimum_reliability_score = float(request.minimum_reliability_score)
            row.notes = request.notes
            row.updated_at = now
        session.commit()
        session.refresh(row)

    _record_governance_event(
        "governance_agent_upserted",
        {
            "active": bool(request.active),
            "allowed_asset_types": list(request.allowed_asset_types or ["CBDC"]),
            "minimum_reliability_score": float(request.minimum_reliability_score),
            "notes": request.notes,
        },
        agent_id=request.agent_id,
    )
    return _to_governance_agent_response(row)

@app.get("/governance/audit", response_model=List[GovernanceEventResponse])
async def list_governance_audit(limit: int = 50):
    with SessionLocal() as session:
        rows = (
            session.execute(
                select(GovernanceEventRow).order_by(desc(GovernanceEventRow.created_at)).limit(max(1, min(int(limit), 200)))
            )
            .scalars()
            .all()
        )
        return [
            GovernanceEventResponse(
                id=int(row.id),
                agent_id=row.agent_id,
                event_type=row.event_type,
                details=row.details or {},
                created_at=row.created_at,
            )
            for row in rows
        ]

@app.post("/secure-aggregation/masks/submit")
async def submit_secure_aggregation_mask(request: SecureAggregationMaskSubmitRequest):
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        existing = (
            session.execute(
                select(SecureAggregationMaskRow)
                .where(SecureAggregationMaskRow.round_id == request.round_id)
                .where(SecureAggregationMaskRow.agent_id == request.agent_id)
            )
            .scalars()
            .first()
        )
        if existing is None:
            existing = SecureAggregationMaskRow(
                round_id=request.round_id,
                agent_id=request.agent_id,
                encrypted_mask_share=request.encrypted_mask_share,
                submitted_at=now,
            )
            session.add(existing)
        else:
            existing.encrypted_mask_share = request.encrypted_mask_share
            existing.submitted_at = now
        session.commit()

    _record_governance_event(
        "secure_aggregation_mask_submitted",
        {"round_id": request.round_id},
        agent_id=request.agent_id,
    )
    return {"status": "stored"}

@app.post("/secure-aggregation/masks/aggregate", response_model=SecureAggregationMaskAggregateResponse)
async def aggregate_secure_aggregation_masks(request: SecureAggregationMaskAggregateRequest):
    try:
        with SessionLocal() as session:
            rows = (
                session.execute(
                    select(SecureAggregationMaskRow).where(SecureAggregationMaskRow.round_id == request.round_id)
                )
                .scalars()
                .all()
            )
        row_map = {row.agent_id: row for row in rows}
        missing_agents = [item.agent_id for item in request.updates if item.agent_id not in row_map]
        if missing_agents:
            raise HTTPException(status_code=400, detail=f"Missing secure aggregation masks for: {', '.join(missing_agents)}")

        mask_payloads: List[bytes] = []
        aggregation_weights: List[float] = []
        for item in request.updates:
            row = row_map[item.agent_id]
            try:
                mask_payload = _decrypt_escrowed_mask_share(row.encrypted_mask_share)
            except HTTPException as exc:
                if "for " not in str(exc.detail):
                    raise HTTPException(status_code=exc.status_code, detail=f"{exc.detail} for {item.agent_id}") from exc
                raise
            mask_payloads.append(mask_payload)
            aggregation_weights.append(_aggregation_weight(item, request.strategy))

        aggregate_mask = _aggregate_mask_payloads(mask_payloads, aggregation_weights)
        return SecureAggregationMaskAggregateResponse(
            aggregate_mask=base64.b64encode(aggregate_mask).decode("ascii"),
            participant_count=len(mask_payloads),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to aggregate secure aggregation masks: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
