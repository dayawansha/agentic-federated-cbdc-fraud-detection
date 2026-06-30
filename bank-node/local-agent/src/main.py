"""
================================================================================
LOCAL AGENT - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Local Agent as the "Manager" and "Autonomous Operator" inside a bank node.
Its primary role is to run local federated training tasks while strictly protecting
the bank's resources, performance, and customer privacy.

The Local Agent works through an autonomous workflow:
1. GATING / SELF-PROTECTION: Before joining a learning round, it evaluates local resources
   (simulated CPU load and battery level) and checks the remaining privacy budget.
   If CPU load is too high (e.g., > 90%), battery is too low (e.g., < 20%), or the privacy
   budget is depleted, the agent self-rejects and declines to join the round.
2. ADAPTIVE PLANNING: If participating, it creates a custom "Local execution plan."
   - If local data lacks fraud labels (sparse labels), it turns on semi-supervised training.
   - If the privacy budget is tight, it increases the differential privacy noise level.
   - If recent GNN performance was low, it schedules more local training epochs.
3. WORKFLOW ORCHESTRATION: The Local Agent compiles a LangGraph workflow:
   - Fetches the latest global weights from the model registry.
   - Triggers the GNN service to train the model on local graph data.
   - Sends the model to the privacy layer to add noise, apply masks, and encrypt weights.
   - Submits the final secure package to the central coordinator.
4. ALERTS AND NEGOTIATION: After a round, it runs model inference on fresh transactions.
   If it detects high-probability fraud, it publishes alerts directly into a Kafka stream.
   It also participates in consensus votes regarding new fraud patterns and model weights.
================================================================================
"""
import logging
import os
import sys
import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
import httpx

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.schemas.models import (
    WeightNegotiationRequest,
    WeightNegotiationResponse,
    FraudPatternProposal,
    ConsensusVote,
)
from shared.reasoning.engine import get_reasoning_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs from environment variables
LOCAL_GNN_URL = os.getenv("LOCAL_GNN_URL", "http://localhost:9002")
PRIVACY_LAYER_URL = os.getenv("PRIVACY_LAYER_URL", "http://localhost:9003")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8001")
MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://localhost:8004")
POLICY_MANAGER_URL = os.getenv("POLICY_MANAGER_URL", "http://localhost:8003")
ENFORCE_PRIVACY_BUDGET = os.getenv("ENFORCE_PRIVACY_BUDGET", "true").strip().lower() not in {"0", "false", "no", "off"}
SIMULATE_LOW_RESOURCES = os.getenv("SIMULATE_LOW_RESOURCES", "false").strip().lower() not in {"0", "false", "no", "off"}
SIMULATE_CPU_LOAD = int(os.getenv("SIMULATE_CPU_LOAD", "45"))
SIMULATE_BATTERY_LEVEL = int(os.getenv("SIMULATE_BATTERY_LEVEL", "80"))
RESOURCE_CPU_REJECTION_THRESHOLD = int(os.getenv("RESOURCE_CPU_REJECTION_THRESHOLD", "90"))
RESOURCE_BATTERY_REJECTION_THRESHOLD = int(os.getenv("RESOURCE_BATTERY_REJECTION_THRESHOLD", "20"))
DP_NOISE_MULTIPLIER = float(os.getenv("DP_NOISE_MULTIPLIER", "0.01"))
PROJECTED_ROUND_EPSILON_SPEND = float(os.getenv("PROJECTED_ROUND_EPSILON_SPEND", "0.1"))
PROJECTED_ROUND_DELTA_SPEND = float(os.getenv("PROJECTED_ROUND_DELTA_SPEND", "0.0"))
MIN_REMAINING_EPSILON_BUFFER = float(os.getenv("MIN_REMAINING_EPSILON_BUFFER", "0.0"))
MIN_REMAINING_EPSILON_RATIO = float(os.getenv("MIN_REMAINING_EPSILON_RATIO", "0.0"))
REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION = os.getenv("REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION", "false").strip().lower() in {"1", "true", "yes", "on"}
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_FRAUD_ALERTS_TOPIC = os.getenv("KAFKA_FRAUD_ALERTS_TOPIC", "fraud.alerts")
AUTO_ALERT_ON_ROUND_COMPLETE = os.getenv("AUTO_ALERT_ON_ROUND_COMPLETE", "true").strip().lower() not in {"0", "false", "no", "off"}
ALERT_CONFIDENCE_THRESHOLD = float(os.getenv("ALERT_CONFIDENCE_THRESHOLD", "0.9"))
ALERT_PUBLISH_LIMIT = int(os.getenv("ALERT_PUBLISH_LIMIT", "5"))
FEDPROX_MU = float(os.getenv("FEDPROX_MU", "1.0"))
DEFAULT_LOCAL_TRAINING_EPOCHS = max(1, int(os.getenv("LOCAL_TRAINING_EPOCHS", "1")))
MAX_ADAPTIVE_LOCAL_EPOCHS = max(DEFAULT_LOCAL_TRAINING_EPOCHS, int(os.getenv("MAX_ADAPTIVE_LOCAL_EPOCHS", "3")))
DEFAULT_PSEUDO_LABEL_WEIGHT = float(os.getenv("PSEUDO_LABEL_WEIGHT", "0.35"))
DEFAULT_PSEUDO_LABEL_CONFIDENCE = float(os.getenv("PSEUDO_LABEL_CONFIDENCE", "0.9"))

# --- LangGraph State Definition ---
class LocalAgentState(TypedDict):
    """
    BUSINESS REASON: Think of this state dictionary as the "flight log" or "ledger" of the
    Local Agent's training run. It holds all the current parameters, trained weights,
    evaluated metrics, resource checks, and planning traces as they pass through the
    orchestrated nodes in the LangGraph execution flow.
    """
    agent_id: str
    round_id: str
    data_ready: bool
    global_model_loaded: bool
    training_complete: bool
    privacy_applied: bool
    raw_weights: bytes
    protected_weights: bytes
    masked_weights: bytes
    encrypted_weights: bytes
    encrypted_mask_share: str
    protected_payload_sha256: str
    encrypted_payload_sha256: str
    sample_size: int
    metrics: Dict[str, float]
    global_weights: bytes
    model_version_id: Optional[str]
    noise_multiplier: float
    selected_strategy: str
    local_training_strategy: str
    fedprox_mu: float
    local_epochs: int
    pseudo_label_weight: float
    pseudo_label_confidence: float
    post_round_inference_limit: int
    run_post_round_inference: bool
    participation_checks: Dict[str, object]
    adaptive_plan: Dict[str, object]
    reasoning_trace: List[str]
    current_step: str


class AgentInferencePrediction(BaseModel):
    """
    BUSINESS REASON: Represents a single predicted fraud warning for a transaction.
    The Local Agent uses this structure to decide whether to publish an alert into the
    Kafka queue.
    """
    tx_id: int
    predicted_class: str
    predicted_label: int
    confidence: float
    illicit_probability: float
    licit_probability: float
    unknown_probability: float
    known_label: Optional[str] = None


class AgentInferenceResponse(BaseModel):
    """
    BUSINESS REASON: Returns a structured summary of model predictions to allow
    the operator or alerting system to analyze current GNN risk assessments.
    """
    status: str
    agent_id: str
    generated_at: str
    prediction_count: int
    predictions: List[AgentInferencePrediction]


class ParticipationDecision(BaseModel):
    """
    BUSINESS REASON: Captures the details of the bank node's decision on whether to join
    a training round. It includes logs of CPU, battery, and privacy budget balances.
    """
    allowed: bool
    reason: str
    checks: Dict[str, object]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _numeric_value(payload: object, key: str, default: float = 0.0) -> float:
    if isinstance(payload, dict):
        value = payload.get(key, default)
        if isinstance(value, (int, float)):
            return float(value)
    return float(default)


def _normalize_inference_prediction(prediction: object) -> Dict[str, object]:
    record = prediction if isinstance(prediction, dict) else {}
    illicit_probability = _clamp(_numeric_value(record, "illicit_probability", 0.0), 0.0, 1.0)
    licit_probability = _clamp(_numeric_value(record, "licit_probability", 0.0), 0.0, 1.0)
    unknown_probability = _clamp(_numeric_value(record, "unknown_probability", 0.0), 0.0, 1.0)
    confidence = _clamp(
        _numeric_value(record, "confidence", max(illicit_probability, licit_probability, unknown_probability)),
        0.0,
        1.0,
    )
    return {
        "tx_id": int(record.get("tx_id", 0)),
        "predicted_class": str(record.get("predicted_class", "unknown")),
        "predicted_label": int(record.get("predicted_label", -1)),
        "confidence": confidence,
        "illicit_probability": illicit_probability,
        "licit_probability": licit_probability,
        "unknown_probability": unknown_probability,
        "known_label": record.get("known_label"),
    }


def _build_local_plan_context(state: LocalAgentState) -> Dict[str, object]:
    checks = state.get("participation_checks", {}) or {}
    return {
        "agent_id": state.get("agent_id", str(agent_status.get("agent_id", "local-agent"))),
        "round_id": state.get("round_id"),
        "selected_strategy": state.get("selected_strategy", "FedAvg"),
        "global_model_loaded": bool(state.get("global_model_loaded", False)),
        "participation_checks": checks,
        "previous_metrics": _coerce_numeric_metrics(agent_status.get("last_metrics")),
        "inference_summary": agent_status.get("last_inference_summary", {}),
        "dp_noise_multiplier": DP_NOISE_MULTIPLIER,
        "default_local_training_epochs": DEFAULT_LOCAL_TRAINING_EPOCHS,
        "max_adaptive_local_epochs": MAX_ADAPTIVE_LOCAL_EPOCHS,
        "fedprox_mu": FEDPROX_MU,
        "pseudo_label_weight_default": DEFAULT_PSEUDO_LABEL_WEIGHT,
        "pseudo_label_confidence_default": DEFAULT_PSEUDO_LABEL_CONFIDENCE,
        "alert_publish_limit": ALERT_PUBLISH_LIMIT,
        "auto_alert_on_round_complete": AUTO_ALERT_ON_ROUND_COMPLETE,
    }


async def _derive_local_training_plan(state: LocalAgentState) -> Dict[str, object]:
    engine = get_reasoning_engine(str(state.get("agent_id", agent_status["agent_id"])), "local_agent")
    decision = await engine.reason_local_training_plan(_build_local_plan_context(state))
    plan = decision.model_dump()
    plan["reasoning_trace"] = list(decision.reasoning_steps)
    return plan

# --- Node Functions ---
async def check_data_availability(state: LocalAgentState):
    logger.info(f"Checking data availability for round {state['round_id']}")
    # In production, check if shard file exists or Neo4j has data
    state['data_ready'] = True
    state['current_step'] = "global_model_fetch"
    return state

async def fetch_latest_global_model(state: LocalAgentState):
    logger.info("Fetching latest global model from Model Registry...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MODEL_REGISTRY_URL}/models/latest/weights", timeout=60.0)
            if response.status_code == 404:
                logger.info("No global model found yet, proceeding with local initialization")
                state["global_weights"] = b""
                state["model_version_id"] = None
                state["global_model_loaded"] = False
            else:
                response.raise_for_status()
                payload = response.json()
                state["global_weights"] = base64.b64decode(payload["weights"])
                state["model_version_id"] = payload.get("version_id")
                state["global_model_loaded"] = True
        except httpx.HTTPStatusError as exc:
            logger.error("Model Registry returned an error while fetching latest model: %s", exc.response.text)
            raise HTTPException(status_code=502, detail="Model Registry latest model request failed") from exc
        except Exception as exc:
            logger.error("Error fetching latest global model: %s", exc)
            state["global_weights"] = b""
            state["model_version_id"] = None
            state["global_model_loaded"] = False

    state["current_step"] = "planning"
    return state


async def plan_local_execution(state: LocalAgentState):
    logger.info("Planning adaptive local execution strategy with autonomous reasoning engine...")
    plan = await _derive_local_training_plan(state)
    state["adaptive_plan"] = plan
    state["reasoning_trace"] = list(plan.get("reasoning_trace", []))
    state["noise_multiplier"] = float(plan.get("noise_multiplier", state.get("noise_multiplier", DP_NOISE_MULTIPLIER)))
    state["local_training_strategy"] = str(plan.get("local_training_strategy", state.get("selected_strategy", "FedAvg")))
    state["fedprox_mu"] = float(plan.get("fedprox_mu", state.get("fedprox_mu", FEDPROX_MU)))
    state["local_epochs"] = int(plan.get("local_epochs", DEFAULT_LOCAL_TRAINING_EPOCHS))
    state["pseudo_label_weight"] = float(plan.get("pseudo_label_weight", 0.0))
    state["pseudo_label_confidence"] = float(plan.get("pseudo_label_confidence", DEFAULT_PSEUDO_LABEL_CONFIDENCE))
    state["run_post_round_inference"] = bool(plan.get("run_post_round_inference", AUTO_ALERT_ON_ROUND_COMPLETE))
    state["post_round_inference_limit"] = int(plan.get("post_round_inference_limit", ALERT_PUBLISH_LIMIT))
    state["current_step"] = "training_triggered"
    return state

async def run_local_training(state: LocalAgentState):
    logger.info("Triggering Local GNN Training...")
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "round_id": state["round_id"],
                "strategy": state.get("local_training_strategy", state.get("selected_strategy", "FedAvg")),
                "fedprox_mu": float(state.get("fedprox_mu", FEDPROX_MU)),
                "epochs": int(state.get("local_epochs", DEFAULT_LOCAL_TRAINING_EPOCHS)),
                "pseudo_label_weight": float(state.get("pseudo_label_weight", 0.0)),
                "pseudo_label_confidence": float(state.get("pseudo_label_confidence", DEFAULT_PSEUDO_LABEL_CONFIDENCE)),
            }
            if state.get("global_weights"):
                payload["global_weights"] = base64.b64encode(state["global_weights"]).decode("ascii")
            response = await client.post(
                f"{LOCAL_GNN_URL}/train",
                json=payload,
                timeout=180.0,
            )
            if response.status_code == 200:
                payload = response.json()
                state["raw_weights"] = base64.b64decode(payload["weights"])
                state["sample_size"] = int(payload.get("sample_size", 0))
                state["metrics"] = payload.get("metrics", {}) or {}
                state["metrics"].update(
                    {
                        "adaptive_epochs": float(state.get("local_epochs", DEFAULT_LOCAL_TRAINING_EPOCHS)),
                        "adaptive_noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                        "adaptive_risk_pressure": _numeric_value(state.get("adaptive_plan"), "risk_pressure", 0.0),
                        "adaptive_budget_pressure": _numeric_value(state.get("adaptive_plan"), "budget_pressure", 0.0),
                        "adaptive_sparse_pressure": _numeric_value(state.get("adaptive_plan"), "sparse_label_pressure", 0.0),
                        "adaptive_plan_confidence": _numeric_value(state.get("adaptive_plan"), "plan_confidence", 0.0),
                        "adaptive_local_fedprox": 1.0 if state.get("local_training_strategy") == "FedProxGNN" else 0.0,
                    }
                )
                state['training_complete'] = True
                logger.info("Local training successful")
            else:
                logger.error(f"Training failed: {response.text}")
        except Exception as e:
            logger.error(f"Error calling GNN service: {e}")
            
    state['current_step'] = "apply_privacy"
    return state

async def apply_privacy_measures(state: LocalAgentState):
    logger.info("Applying Differential Privacy and Encryption...")
    async with httpx.AsyncClient() as client:
        try:
            # Call Privacy Layer to apply DP
            dp_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/apply-dp",
                json={
                    "weights": base64.b64encode(state.get("raw_weights", b"")).decode("ascii"),
                    "noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                },
                timeout=180.0,
            )
            if dp_response.status_code == 200:
                dp_payload = dp_response.json()
                state["protected_weights"] = base64.b64decode(dp_payload["weights"])
                state['privacy_applied'] = True
                logger.info("Privacy measures applied successfully")
            else:
                logger.error(f"Privacy application failed: {dp_response.text}")

            secure_update_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/prepare-secure-update",
                json={
                    "round_id": state["round_id"],
                    "agent_id": state["agent_id"],
                    "weights": base64.b64encode(state.get("protected_weights", b"")).decode("ascii"),
                },
                timeout=180.0,
            )
            if secure_update_response.status_code == 200:
                secure_payload = secure_update_response.json()
                masked_weights_b64 = secure_payload.get("masked_weights", "")
                state["masked_weights"] = base64.b64decode(masked_weights_b64) if masked_weights_b64 else state.get("protected_weights", b"")
                state["encrypted_mask_share"] = secure_payload.get("encrypted_mask_share", "")
            else:
                logger.error(f"Secure aggregation preparation failed: {secure_update_response.text}")
                state["masked_weights"] = state.get("protected_weights", b"")
                state["encrypted_mask_share"] = ""

            encrypt_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/encrypt",
                json={"data": base64.b64encode(state.get("masked_weights", b"")).decode("ascii")},
                timeout=180.0,
            )
            if encrypt_response.status_code == 200:
                encrypt_payload = encrypt_response.json()
                state["encrypted_weights"] = base64.b64decode(encrypt_payload["encrypted_data"])
            else:
                logger.error(f"Encryption failed: {encrypt_response.text}")

            if state.get("protected_weights"):
                protected_weights_b64 = base64.b64encode(state.get("masked_weights", b"")).decode("ascii")
                encrypted_weights_b64 = base64.b64encode(state.get("encrypted_weights", b"")).decode("ascii")
                state["protected_payload_sha256"] = hashlib.sha256(protected_weights_b64.encode("ascii")).hexdigest()
                state["encrypted_payload_sha256"] = hashlib.sha256(encrypted_weights_b64.encode("ascii")).hexdigest() if encrypted_weights_b64 else ""

                evaluation_response = await client.post(
                    f"{PRIVACY_LAYER_URL}/privacy/evaluate",
                    json={
                        "raw_weights": base64.b64encode(state.get("raw_weights", b"")).decode("ascii"),
                        "protected_weights": protected_weights_b64,
                        "encrypted_data": encrypted_weights_b64,
                        "noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                    },
                    timeout=180.0,
                )
                if evaluation_response.status_code == 200:
                    evaluation = evaluation_response.json()
                    state["metrics"].update(
                        {
                            "privacy_byte_change_ratio": float(evaluation.get("byte_change_ratio", 0.0)),
                            "privacy_size_overhead_ratio": float(evaluation.get("size_overhead_ratio", 0.0)),
                            "privacy_tensor_l2_delta": float(evaluation.get("tensor_l2_delta", 0.0)),
                            "privacy_tensor_change_ratio": float(evaluation.get("tensor_change_ratio", 0.0)),
                        }
                    )
                else:
                    logger.error("Privacy evaluation failed: %s", evaluation_response.text)
        except Exception as e:
            logger.error(f"Error calling Privacy service: {e}")

    state['current_step'] = "submitting_update"
    return state

async def submit_update_to_coordinator(state: LocalAgentState):
    logger.info("Submitting model update to Coordinator...")
    async with httpx.AsyncClient() as client:
        try:
            metrics = {
                key: float(value)
                for key, value in (state.get("metrics", {}) or {}).items()
                if isinstance(value, (int, float)) and value is not None
            }
            payload = {
                "agent_id": state["agent_id"],
                "round_id": state["round_id"],
                "weights": base64.b64encode(state.get("masked_weights", b"")).decode("ascii"),
                "encrypted_weights": base64.b64encode(state.get("encrypted_weights", b"")).decode("ascii"),
                "encrypted_mask_share": state.get("encrypted_mask_share", ""),
                "protected_payload_sha256": state.get("protected_payload_sha256"),
                "encrypted_payload_sha256": state.get("encrypted_payload_sha256"),
                "sample_size": int(state.get("sample_size", 0)),
                "metrics": metrics,
                "privacy_applied": bool(state.get("privacy_applied", False)),
                "encryption_applied": bool(state.get("encrypted_weights")),
                "noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                "model_version_id": state.get("model_version_id"),
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            resp = await client.post(f"{COORDINATOR_URL}/updates/submit", json=payload, timeout=60.0)
            if resp.status_code != 200:
                logger.error(f"Coordinator update submission failed: {resp.text}")
        except Exception as e:
            logger.error(f"Error submitting update to Coordinator: {e}")

    if state.get("run_post_round_inference", AUTO_ALERT_ON_ROUND_COMPLETE):
        try:
            inference_response = await fetch_inference_predictions(limit=int(state.get("post_round_inference_limit", ALERT_PUBLISH_LIMIT)))
            publish_inference_alerts(state["agent_id"], inference_response.predictions)
        except Exception as exc:
            logger.warning("Inference-driven alert publication skipped: %s", exc)

    state["current_step"] = "done"
    return state

# --- Graph Construction ---
workflow = StateGraph(LocalAgentState)
workflow.add_node("check_data", check_data_availability)
workflow.add_node("fetch_global_model", fetch_latest_global_model)
workflow.add_node("plan_execution", plan_local_execution)
workflow.add_node("train", run_local_training)
workflow.add_node("privacy", apply_privacy_measures)
workflow.add_node("submit_update", submit_update_to_coordinator)

workflow.set_entry_point("check_data")
workflow.add_edge("check_data", "fetch_global_model")
workflow.add_edge("fetch_global_model", "plan_execution")
workflow.add_edge("plan_execution", "train")
workflow.add_edge("train", "privacy")
workflow.add_edge("privacy", "submit_update")
workflow.add_edge("submit_update", END)

app_graph = workflow.compile()

# --- FastAPI Setup ---
app = FastAPI(title="Local Agent Service")

agent_status: Dict[str, object] = {
    "agent_id": os.getenv("AGENT_ID", "local-agent"),
    "last_round_id": None,
    "last_update_at": None,
    "last_metrics": {},
    "last_model_version": None,
    "last_alert_publish_at": None,
    "last_alert_publish_count": 0,
    "last_inference_at": None,
    "last_inference_summary": {},
    "last_participation_decision": None,
    "last_adaptive_plan": {},
    "last_reasoning_trace": [],
    "reasoning_provider": "expert-inference",
}

def _coerce_numeric_metrics(payload: Optional[Dict[str, object]]) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for key, value in (payload or {}).items():
        if isinstance(value, (int, float)) and value is not None:
            metrics[str(key)] = float(value)
    return metrics


async def _hydrate_agent_status_from_latest_registry_model() -> None:
    logger.info("Local Agent starting up. Querying latest model version from Model Registry...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MODEL_REGISTRY_URL}/models/latest", timeout=5.0)
            if response.status_code == 200:
                payload = response.json()
                version_id = payload.get("version_id")
                if version_id:
                    agent_status["last_model_version"] = version_id
                    logger.info(f"Loaded active model version on startup: {version_id}")
                agent_status["last_metrics"] = _coerce_numeric_metrics(payload.get("metrics"))
            else:
                logger.info(f"Could not load latest model version on startup (Model Registry returned {response.status_code})")
        except Exception as e:
            logger.warning(f"Failed to query latest model version on startup (registry might be offline or empty): {e}")

def _severity_for_confidence(confidence: float) -> str:
    if confidence >= 0.98:
        return "critical"
    if confidence >= 0.93:
        return "high"
    if confidence >= ALERT_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _reject_participation(reason: str, checks: Dict[str, object]) -> ParticipationDecision:
    return ParticipationDecision(allowed=False, reason=reason, checks=checks)


async def evaluate_participation_constraints(agent_id: str) -> ParticipationDecision:
    checks: Dict[str, object] = {
        "privacy_budget": {
            "enforced": ENFORCE_PRIVACY_BUDGET,
            "projected_round_epsilon_spend": PROJECTED_ROUND_EPSILON_SPEND,
            "projected_round_delta_spend": PROJECTED_ROUND_DELTA_SPEND,
        },
        "resource_guardrails": {
            "enabled": SIMULATE_LOW_RESOURCES,
            "cpu_load": SIMULATE_CPU_LOAD,
            "battery_level": SIMULATE_BATTERY_LEVEL,
            "cpu_threshold": RESOURCE_CPU_REJECTION_THRESHOLD,
            "battery_threshold": RESOURCE_BATTERY_REJECTION_THRESHOLD,
        },
        "policy_constraints": {},
    }

    if ENFORCE_PRIVACY_BUDGET or REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION:
        async with httpx.AsyncClient() as client:
            try:
                budget_response = await client.get(f"{POLICY_MANAGER_URL}/policies/budget/{agent_id}", timeout=10.0)
                budget_response.raise_for_status()
                budget = budget_response.json()

                epsilon = float(budget.get("epsilon", 10.0))
                delta = float(budget.get("delta", 1e-5))
                spent_epsilon = float(budget.get("total_spent_epsilon", 0.0))
                spent_delta = float(budget.get("total_spent_delta", 0.0))
                remaining_epsilon = epsilon - spent_epsilon
                remaining_delta = delta - spent_delta
                required_reserve = max(MIN_REMAINING_EPSILON_BUFFER, epsilon * MIN_REMAINING_EPSILON_RATIO)

                checks["privacy_budget"].update(
                    {
                        "epsilon": epsilon,
                        "delta": delta,
                        "spent_epsilon": spent_epsilon,
                        "spent_delta": spent_delta,
                        "remaining_epsilon": remaining_epsilon,
                        "remaining_delta": remaining_delta,
                        "required_reserve_epsilon": required_reserve,
                    }
                )

                if ENFORCE_PRIVACY_BUDGET:
                    if remaining_epsilon < PROJECTED_ROUND_EPSILON_SPEND:
                        return _reject_participation(
                            "Participation rejected: Insufficient privacy budget for projected round cost",
                            checks,
                        )
                    if remaining_epsilon - PROJECTED_ROUND_EPSILON_SPEND < required_reserve:
                        return _reject_participation(
                            "Participation rejected: Privacy reserve would fall below policy buffer",
                            checks,
                        )
                    if remaining_delta < PROJECTED_ROUND_DELTA_SPEND:
                        return _reject_participation(
                            "Participation rejected: Insufficient delta budget for projected round cost",
                            checks,
                        )
            except httpx.HTTPStatusError as exc:
                logger.warning("Policy manager budget lookup failed for %s: %s", agent_id, exc.response.text)
                checks["privacy_budget"]["error"] = f"budget lookup failed with status {exc.response.status_code}"
                if REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION:
                    return _reject_participation("Participation rejected: Policy manager budget check unavailable", checks)
            except Exception as exc:
                logger.warning("Failed to query budget from policy manager: %s", exc)
                checks["privacy_budget"]["error"] = str(exc)
                if REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION:
                    return _reject_participation("Participation rejected: Policy manager budget check unavailable", checks)

            try:
                policy_response = await client.get(f"{POLICY_MANAGER_URL}/policies/global", timeout=10.0)
                policy_response.raise_for_status()
                policies = policy_response.json()
                min_noise = float(policies.get("min_noise_multiplier", 0.0))
                max_noise = float(policies.get("max_noise_multiplier", 1.0))
                require_encrypted_updates = bool(policies.get("require_encrypted_updates", True))

                checks["policy_constraints"].update(
                    {
                        "min_noise_multiplier": min_noise,
                        "max_noise_multiplier": max_noise,
                        "configured_noise_multiplier": DP_NOISE_MULTIPLIER,
                        "require_encrypted_updates": require_encrypted_updates,
                    }
                )

                if DP_NOISE_MULTIPLIER < min_noise or DP_NOISE_MULTIPLIER > max_noise:
                    return _reject_participation(
                        "Participation rejected: Configured noise multiplier violates global policy",
                        checks,
                    )
            except httpx.HTTPStatusError as exc:
                logger.warning("Global policy lookup failed for %s: %s", agent_id, exc.response.text)
                checks["policy_constraints"]["error"] = f"global policy lookup failed with status {exc.response.status_code}"
                if REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION:
                    return _reject_participation("Participation rejected: Global policy check unavailable", checks)
            except Exception as exc:
                logger.warning("Failed to query global policy from policy manager: %s", exc)
                checks["policy_constraints"]["error"] = str(exc)
                if REQUIRE_POLICY_MANAGER_FOR_PARTICIPATION:
                    return _reject_participation("Participation rejected: Global policy check unavailable", checks)

    if SIMULATE_LOW_RESOURCES:
        if (
            SIMULATE_CPU_LOAD > RESOURCE_CPU_REJECTION_THRESHOLD
            or SIMULATE_BATTERY_LEVEL < RESOURCE_BATTERY_REJECTION_THRESHOLD
        ):
            return _reject_participation(
                "Participation rejected: Node resources exhausted (simulated CPU/Battery constraint)",
                checks,
            )

    engine = get_reasoning_engine(agent_id, "local_agent")
    reasoning = await engine.reason_participation(
        {
            "agent_id": agent_id,
            "hard_constraints_passed": True,
            "hard_constraint_reason": "Participation approved",
            "checks": checks,
            "last_metrics": agent_status.get("last_metrics", {}),
            "last_inference_summary": agent_status.get("last_inference_summary", {}),
        }
    )
    checks["autonomous_reasoning"] = reasoning.model_dump()
    agent_status["reasoning_provider"] = reasoning.provider
    if not reasoning.participate:
        return _reject_participation(
            reasoning.rationale_summary or "Participation rejected by autonomous reasoning engine",
            checks,
        )

    return ParticipationDecision(
        allowed=True,
        reason=reasoning.rationale_summary or "Participation approved by autonomous reasoning engine",
        checks=checks,
    )

def _build_alerts_from_predictions(agent_id: str, predictions: List[AgentInferencePrediction]) -> List[Dict[str, object]]:
    alerts: List[Dict[str, object]] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for prediction in predictions:
        if str(prediction.predicted_class).lower() != "illicit":
            continue
        confidence = float(prediction.confidence)
        if confidence < ALERT_CONFIDENCE_THRESHOLD:
            continue
        alerts.append(
            {
                "alert_id": f"{agent_id}-{prediction.tx_id}-{uuid.uuid4().hex[:8]}",
                "txId": int(prediction.tx_id),
                "timestamp": timestamp,
                "severity": _severity_for_confidence(confidence),
                "confidence_score": confidence,
                "reason": f"Local GNN predicted illicit activity with confidence {confidence:.4f}",
                "status": "open",
                "source": "local-agent-inference",
                "agent_id": agent_id,
            }
        )
        if len(alerts) >= ALERT_PUBLISH_LIMIT:
            break
    return alerts

def publish_inference_alerts(agent_id: str, predictions: List[AgentInferencePrediction]) -> int:
    alerts = _build_alerts_from_predictions(agent_id, predictions)
    if not alerts:
        return 0

    try:
        from confluent_kafka import Producer
    except Exception as exc:
        logger.warning("Kafka producer unavailable for inference alert publishing: %s", exc)
        return 0

    producer = Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": f"{agent_id}-inference-alert-publisher",
        }
    )
    for alert in alerts:
        producer.produce(
            KAFKA_FRAUD_ALERTS_TOPIC,
            key=str(alert["alert_id"]),
            value=json.dumps(alert),
        )
        producer.poll(0)
    producer.flush(5.0)

    published_at = datetime.now(timezone.utc).isoformat()
    agent_status["last_alert_publish_at"] = published_at
    agent_status["last_alert_publish_count"] = len(alerts)
    logger.info("Published %s inference-driven alert(s) for agent %s", len(alerts), agent_id)
    return len(alerts)


async def fetch_inference_predictions(limit: int = 10, tx_ids: Optional[List[int]] = None) -> AgentInferenceResponse:
    payload: Dict[str, object] = {"limit": max(1, min(int(limit), 50))}
    if tx_ids:
        payload["tx_ids"] = [int(tx_id) for tx_id in tx_ids]

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{LOCAL_GNN_URL}/infer", json=payload, timeout=180.0)
            response.raise_for_status()
            inference_payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Local GNN inference request failed: %s", exc.response.text)
            raise HTTPException(status_code=502, detail="Local GNN inference request failed") from exc
        except Exception as exc:
            logger.error("Error calling Local GNN inference: %s", exc)
            raise HTTPException(status_code=502, detail="Local GNN inference service unreachable") from exc

    raw_predictions = inference_payload.get("predictions") or []
    predictions = [AgentInferencePrediction(**_normalize_inference_prediction(prediction)) for prediction in raw_predictions]
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "prediction_count": len(predictions),
        "high_risk_count": sum(1 for prediction in predictions if prediction.predicted_class == "illicit"),
        "top_tx_id": predictions[0].tx_id if predictions else None,
        "top_confidence": predictions[0].confidence if predictions else None,
    }
    agent_status["last_inference_at"] = generated_at
    agent_status["last_inference_summary"] = summary

    return AgentInferenceResponse(
        status="success",
        agent_id=str(agent_status["agent_id"]),
        generated_at=generated_at,
        prediction_count=len(predictions),
        predictions=predictions,
    )

@app.get("/health")
async def health_check():
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by orchestrators or coordinator monitors
    to check that the local agent service is healthy, alive, and listening on its HTTP port.
    """
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    await _hydrate_agent_status_from_latest_registry_model()

@app.get("/agent/status")
async def get_status():
    """
    BUSINESS PURPOSE / REASON: This endpoint allows the dashboard or coordinator to fetch the 
    current status, metrics, adaptive planning traces, and recent round statistics of this node.
    """
    return agent_status


@app.get("/agent/inference", response_model=AgentInferenceResponse)
async def get_agent_inference(limit: int = 10):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the dashboard or compliance systems
    to fetch real-time GNN fraud prediction probabilities for the most suspicious local transactions.
    """
    return await fetch_inference_predictions(limit=limit)

@app.post("/agent/round/start")
async def start_local_round(round_id: str, agent_id: str, selected_strategy: str = "FedAvg", fedprox_mu: Optional[float] = None):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the Central Coordinator to command
    the bank node to begin a training round. It checks battery, CPU, and privacy limits,
    loads the latest global model, triggers training, applies privacy masks, and registers the update.
    """
    logger.info(f"Local Agent {agent_id} starting round {round_id}")
    decision = await evaluate_participation_constraints(agent_id)
    agent_status["last_participation_decision"] = {
        "round_id": round_id,
        "agent_id": agent_id,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "checks": decision.checks,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not decision.allowed:
        logger.warning("Participation rejected for %s: %s", agent_id, decision.reason)
        raise HTTPException(status_code=403, detail=decision.reason)

    initial_state: LocalAgentState = {
        "agent_id": agent_id,
        "round_id": round_id,
        "data_ready": False,
        "global_model_loaded": False,
        "training_complete": False,
        "privacy_applied": False,
        "raw_weights": b"",
        "protected_weights": b"",
        "masked_weights": b"",
        "encrypted_weights": b"",
        "encrypted_mask_share": "",
        "protected_payload_sha256": "",
        "encrypted_payload_sha256": "",
        "sample_size": 0,
        "metrics": {},
        "global_weights": b"",
        "model_version_id": None,
        "noise_multiplier": DP_NOISE_MULTIPLIER,
        "selected_strategy": selected_strategy,
        "local_training_strategy": selected_strategy,
        "fedprox_mu": float(fedprox_mu if fedprox_mu is not None else FEDPROX_MU),
        "local_epochs": DEFAULT_LOCAL_TRAINING_EPOCHS,
        "pseudo_label_weight": 0.0,
        "pseudo_label_confidence": DEFAULT_PSEUDO_LABEL_CONFIDENCE,
        "post_round_inference_limit": ALERT_PUBLISH_LIMIT,
        "run_post_round_inference": AUTO_ALERT_ON_ROUND_COMPLETE,
        "participation_checks": dict(decision.checks),
        "adaptive_plan": {},
        "reasoning_trace": [],
        "current_step": "init"
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    agent_status["agent_id"] = agent_id
    agent_status["last_round_id"] = round_id
    agent_status["last_update_at"] = datetime.now(timezone.utc).isoformat()
    local_metrics = final_state.get("metrics", {}) if isinstance(final_state, dict) else {}
    agent_status["last_metrics"] = local_metrics
    agent_status["last_model_version"] = final_state.get("model_version_id") if isinstance(final_state, dict) else None
    agent_status["last_adaptive_plan"] = final_state.get("adaptive_plan", {}) if isinstance(final_state, dict) else {}
    agent_status["last_reasoning_trace"] = final_state.get("reasoning_trace", []) if isinstance(final_state, dict) else []

    # Re-hydrate from the model registry so agent_status reflects the globally
    # aggregated metrics (registered by the coordinator) rather than only the
    # local GNN training metrics.  This is a best-effort update; failures are
    # silent so they never block the round response.
    try:
        async with httpx.AsyncClient() as _reg_client:
            _reg_resp = await _reg_client.get(f"{MODEL_REGISTRY_URL}/models/latest", timeout=5.0)
            if _reg_resp.status_code == 200:
                _reg_payload = _reg_resp.json()
                _reg_metrics = _coerce_numeric_metrics(_reg_payload.get("metrics"))
                _reg_version = _reg_payload.get("version_id")
                if _reg_metrics:
                    # Registry has real metrics — prefer them as the canonical source.
                    agent_status["last_metrics"] = _reg_metrics
                    logger.info(
                        "Post-round status hydrated from model registry (version=%s, accuracy=%.4f)",
                        _reg_version,
                        _reg_metrics.get("accuracy", 0.0),
                    )
                if _reg_version:
                    agent_status["last_model_version"] = _reg_version
    except Exception as _hydrate_exc:
        logger.debug("Post-round model registry hydration skipped: %s", _hydrate_exc)
    return {
        "status": "success",
        "final_state": {
            "agent_id": final_state.get("agent_id"),
            "round_id": final_state.get("round_id"),
            "current_step": final_state.get("current_step"),
            "data_ready": final_state.get("data_ready"),
            "global_model_loaded": final_state.get("global_model_loaded"),
            "training_complete": final_state.get("training_complete"),
            "privacy_applied": final_state.get("privacy_applied"),
            "sample_size": final_state.get("sample_size"),
            "model_version_id": final_state.get("model_version_id"),
            "metrics": final_state.get("metrics", {}),
            "adaptive_plan": final_state.get("adaptive_plan", {}),
            "reasoning_trace": final_state.get("reasoning_trace", []),
        },
    }

@app.post("/agent/negotiate/propose-weights", response_model=WeightNegotiationResponse)
async def propose_weights(request: WeightNegotiationRequest):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the Central Coordinator during weight negotiation.
    It evaluates the other participant banks' metrics (e.g. F1-score, sample size, reliability) and calculates
    what weighting they should have in model aggregation to ensure fair and accurate collaborative learning.
    """
    logger.info(f"Local Agent negotiating weights for round {request.round_id}")
    proposed_weights = {}
    scores = {}
    for agent in request.agents:
        f1 = agent.metrics.get("f1_score", 0.8)
        if f1 is None:
            f1 = 0.8
        f1 = max(0.01, min(1.0, float(f1)))
        
        reliability = agent.reliability_score
        if reliability is None:
            reliability = 1.0
        reliability = max(0.1, min(1.0, float(reliability)))
        
        sample_size = agent.sample_size
        if sample_size is None or sample_size < 1:
            sample_size = 1
            
        scores[agent.agent_id] = float(sample_size) * f1 * reliability

    total_score = sum(scores.values())
    for agent_id, score in scores.items():
        proposed_weights[agent_id] = score / total_score if total_score > 0 else 1.0 / len(request.agents)

    my_id = str(agent_status.get("agent_id", "local-agent"))
    return WeightNegotiationResponse(agent_id=my_id, proposed_weights=proposed_weights)


@app.post("/agent/consensus/evaluate-pattern", response_model=ConsensusVote)
async def evaluate_pattern(proposal: FraudPatternProposal):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the Central Coordinator during consensus voting.
    It checks proposed new fraud pattern detection rules (like features thresholds or velocity counts)
    against safety boundaries, voting to APPROVE or REJECT the proposal to govern the global policy.
    """
    logger.info(f"Local Agent evaluating fraud pattern proposal {proposal.proposal_id} ({proposal.pattern_name})")
    vote = "APPROVE"
    reason = "All pattern indicators are within valid statistical and structural ranges"
    
    for key, val in proposal.feature_indicators.items():
        val = float(val)
        if "ratio" in key or "score" in key or "probability" in key or "percent" in key:
            if val < 0.0 or val > 1.0:
                vote = "REJECT"
                reason = f"Indicator {key} value {val} is out of bounds [0, 1]"
                break
        if "threshold" in key or "velocity" in key or "count" in key:
            if val < 0.0:
                vote = "REJECT"
                reason = f"Indicator {key} value {val} cannot be negative"
                break
                
    my_id = str(agent_status.get("agent_id", "local-agent"))
    return ConsensusVote(agent_id=my_id, proposal_id=proposal.proposal_id, vote=vote, reason=reason)


@app.post("/agent/consensus/propose-pattern")
async def propose_pattern(proposal_data: dict):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the local bank's compliance officer or dashboard
    to propose a new fraud pattern rule to the federated network, initiating a democratic vote.
    """
    proposal_id = f"prop-{uuid.uuid4().hex[:8]}"
    my_id = str(agent_status.get("agent_id", "local-agent"))
    proposal = FraudPatternProposal(
        proposal_id=proposal_id,
        proposer_id=my_id,
        pattern_name=proposal_data.get("pattern_name", "Unknown Pattern"),
        feature_indicators=proposal_data.get("feature_indicators", {}),
        rationale=proposal_data.get("rationale", "No rationale provided")
    )
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{COORDINATOR_URL}/consensus/propose-fraud-pattern", json=proposal.model_dump(mode="json"), timeout=60.0)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
        except Exception as e:
            logger.error(f"Failed to propose pattern to coordinator: {e}")
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
