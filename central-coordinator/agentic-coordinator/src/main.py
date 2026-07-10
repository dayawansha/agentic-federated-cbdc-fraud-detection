"""
================================================================================
AGENTIC COORDINATOR - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of this service as the "conductor" or the "referee" of a cooperative project
shared among multiple banks. 

In a traditional setup, to teach an AI how to detect transaction fraud (CBDC fraud), 
everyone would have to send their private customer transactions to a single server.
But privacy laws and security rules forbid banks from sharing their private ledger records.

Federated Learning solves this:
1. Each bank keeps its data safe at home and trains its own local AI model.
2. The banks only share the "learnings" (called model weights or updates) — NOT the transaction data.
3. This Coordinator orchestrates the process of combining those updates.

THE COORDINATOR'S CORE STEPS:
1. SELECTING AGENTS: The Coordinator asks the banks if they are ready, healthy, and have enough
   privacy budget (allowance for information leak) and battery/power to participate.
2. TRIGGERING TRAINING: It tells the selected banks to start training their local AI.
3. WAITING FOR UPDATES: It waits for the banks to send back their model updates.
4. SCREENING & GOVERNANCE: It checks if any bank's update looks suspicious or incorrect
   (e.g., if a hacker is trying to upload a "poisoned" model to bypass fraud detection).
5. WEIGHT CONSENSUS: The banks negotiate and vote on how much importance (weight) to give to 
   each other's updates based on their local metrics and reliability.
6. GLOBAL AGGREGATION: The Coordinator triggers the model aggregator to combine these safe updates
   and registers the new global model version for everyone to use.
================================================================================
"""
import logging
import os
import sys
import hashlib
import base64
import io
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple, TypedDict
from langgraph.graph import StateGraph, END
import asyncio
import httpx
from datetime import datetime, timezone
try:
    import redis
except Exception:  # pragma: no cover - optional dependency in tests
    redis = None

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.schemas.models import (
    WeightNegotiationRequest,
    WeightNegotiationItem,
    WeightNegotiationResponse,
    FraudPatternProposal,
    ConsensusVote,
)
from shared.reasoning.engine import get_reasoning_engine
from shared.reasoning.inference_rules import infer_aggregation_strategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configuration
LOCAL_AGENT_URLS = os.getenv("LOCAL_AGENT_URLS", "http://localhost:9001").split(",")
FEDERATED_MODEL_AGGREGATOR_URL = os.getenv("FEDERATED_MODEL_AGGREGATOR_URL", "http://localhost:8002")
POLICY_MANAGER_URL = os.getenv("POLICY_MANAGER_URL", "http://localhost:8003")
MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://localhost:8004")
ROUND_WAIT_SECONDS = float(os.getenv("ROUND_WAIT_SECONDS", "300"))
AGENT_HEALTH_TIMEOUT_SECONDS = float(os.getenv("AGENT_HEALTH_TIMEOUT_SECONDS", "10"))
AGENT_STATUS_TIMEOUT_SECONDS = float(os.getenv("AGENT_STATUS_TIMEOUT_SECONDS", "10"))
REQUIRE_AGENT_HEALTHY = os.getenv("REQUIRE_AGENT_HEALTHY", "true").strip().lower() not in {"0", "false", "no", "off"}
REQUIRE_AGENT_RUNTIME_STATUS = os.getenv("REQUIRE_AGENT_RUNTIME_STATUS", "true").strip().lower() not in {"0", "false", "no", "off"}
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
ENABLE_MODEL_DELTA_SCREENING = os.getenv("ENABLE_MODEL_DELTA_SCREENING", "true").strip().lower() not in {"0", "false", "no", "off"}
MODEL_DELTA_MIN_UPDATES = max(3, int(os.getenv("MODEL_DELTA_MIN_UPDATES", "3")))
MODEL_DELTA_MAD_MULTIPLIER = float(os.getenv("MODEL_DELTA_MAD_MULTIPLIER", "6.0"))
MODEL_DELTA_MIN_COSINE_SIMILARITY = float(os.getenv("MODEL_DELTA_MIN_COSINE_SIMILARITY", "-0.15"))


class WorkflowStateStore:
    """
    BUSINESS REASON: The coordinator needs a reliable way to save and reload the state of
    active federated rounds across restarts or container scale-ups. This class wraps Redis (or
    falls back to in-memory storage) to persist round configurations, submitted agent updates,
    and performance profiles.
    """
    def __init__(self):
        self.available = False
        self.client = None
        if not REDIS_ENABLED or redis is None:
            return
        try:
            if REDIS_URL:
                self.client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            else:
                self.client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
            self.client.ping()
            self.available = True
            logger.info("Agentic coordinator connected to Redis workflow store")
        except Exception as exc:
            self.client = None
            self.available = False
            logger.warning("Redis workflow store unavailable, falling back to in-memory state only: %s", exc)

    def save_json(self, key: str, value: Any) -> None:
        if not self.available or self.client is None:
            return
        self.client.set(key, json.dumps(value))

    def load_json(self, key: str, default: Any) -> Any:
        if not self.available or self.client is None:
            return default
        payload = self.client.get(key)
        if payload is None:
            return default
        try:
            return json.loads(payload)
        except Exception:
            return default

class UpdateSubmission(BaseModel):
    """
    BUSINESS REASON: This schema models a single GNN update package submitted by a bank node.
    It contains:
    - 'agent_id': Which bank node is submitting.
    - 'weights': The trained parameters (possibly masked for secure aggregation).
    - 'encrypted_weights': Fully encrypted parameters (if transport encryption is used).
    - 'encrypted_mask_share': The encrypted seed used to cancel out noise in secure aggregation.
    - 'metrics': Local GNN accuracy and loss to judge model quality.
    - 'sample_size': The amount of transaction data the bank used (vital for volume-based weighting).
    """
    agent_id: str
    round_id: str
    weights: str
    encrypted_weights: Optional[str] = None
    encrypted_mask_share: Optional[str] = None
    protected_payload_sha256: Optional[str] = None
    encrypted_payload_sha256: Optional[str] = None
    sample_size: int
    metrics: Dict[str, float] = {}
    privacy_applied: bool = False
    encryption_applied: bool = False
    noise_multiplier: Optional[float] = None
    model_version_id: Optional[str] = None
    client_timestamp: Optional[str] = None

class SubmissionAck(BaseModel):
    """
    BUSINESS REASON: Standard response sent to bank nodes when they submit GNN weights.
    It lets the bank know if its parameters were successfully received or rejected due to safety checks.
    """
    accepted: bool
    message: str

round_updates: Dict[str, List[UpdateSubmission]] = {}
round_expected_agents: Dict[str, List[str]] = {}
round_events: Dict[str, asyncio.Event] = {}
agent_profiles: Dict[str, Dict[str, float]] = {}
round_state_snapshots: Dict[str, Dict[str, Any]] = {}
WORKFLOW_STATE_STORE = WorkflowStateStore()
WORKFLOW_STATE_UPDATES_KEY = "agentic-coordinator:round_updates"
WORKFLOW_STATE_EXPECTED_KEY = "agentic-coordinator:round_expected_agents"
WORKFLOW_STATE_PROFILES_KEY = "agentic-coordinator:agent_profiles"
WORKFLOW_STATE_SNAPSHOTS_KEY = "agentic-coordinator:round_state_snapshots"
SUPPORTED_AGGREGATION_STRATEGIES = {
    "FedAvg",
    "WeightedFedAvg",
    "PerformanceWeightedFedAvg",
    "AdaptiveFedAvg",
    "FedProxGNN",
    "FedGraph",
    "RobustMedian",
}
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

# --- LangGraph State Definition ---
class AgentState(TypedDict):
    """
    BUSINESS REASON: The Coordinator uses a state-machine (orchestrated via LangGraph)
    to manage the workflow of a federated learning round. This state tracks active participants,
    received model updates, updates that passed outlier screening, the negotiated weights,
    and status flags indicating round progress.
    """
    round_id: str
    active_agents: List[str]
    updates_received: List[UpdateSubmission]
    valid_updates: List[UpdateSubmission]
    rejected_updates: List[Dict[str, Any]]
    aggregation_complete: bool
    metrics: Dict[str, float]
    policies: Dict[str, Any]
    selected_strategy: str
    current_step: str
    negotiated_weights: Optional[Dict[str, float]]
    reasoning_trace: List[str]
    reasoning_provider: str


def _submission_to_payload(update: UpdateSubmission) -> Dict[str, Any]:
    return update.model_dump(mode="json")


def _submission_from_payload(payload: Dict[str, Any]) -> UpdateSubmission:
    return UpdateSubmission(**payload)


def _build_round_state_snapshot(round_id: str, state: Optional[AgentState] = None) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "round_id": round_id,
        "expected_agents": list(round_expected_agents.get(round_id, [])),
        "update_count": len(round_updates.get(round_id, [])),
        "current_step": "unknown",
        "active_agents": [],
        "metrics": {},
        "aggregation_complete": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if state:
        snapshot.update(
            {
                "current_step": state.get("current_step", "unknown"),
                "active_agents": list(state.get("active_agents", [])),
                "metrics": dict(state.get("metrics", {}) or {}),
                "aggregation_complete": bool(state.get("aggregation_complete", False)),
                "selected_strategy": state.get("selected_strategy"),
            }
        )
    return snapshot


def _persist_workflow_state(round_id: Optional[str] = None, state: Optional[AgentState] = None) -> None:
    if round_id:
        round_state_snapshots[round_id] = _build_round_state_snapshot(round_id, state)
    if not WORKFLOW_STATE_STORE.available:
        return
    WORKFLOW_STATE_STORE.save_json(
        WORKFLOW_STATE_UPDATES_KEY,
        {rid: [_submission_to_payload(update) for update in updates] for rid, updates in round_updates.items()},
    )
    WORKFLOW_STATE_STORE.save_json(WORKFLOW_STATE_EXPECTED_KEY, round_expected_agents)
    WORKFLOW_STATE_STORE.save_json(WORKFLOW_STATE_PROFILES_KEY, agent_profiles)
    WORKFLOW_STATE_STORE.save_json(WORKFLOW_STATE_SNAPSHOTS_KEY, round_state_snapshots)


def _load_persisted_workflow_state() -> None:
    if not WORKFLOW_STATE_STORE.available:
        return
    loaded_updates = WORKFLOW_STATE_STORE.load_json(WORKFLOW_STATE_UPDATES_KEY, {})
    loaded_expected = WORKFLOW_STATE_STORE.load_json(WORKFLOW_STATE_EXPECTED_KEY, {})
    loaded_profiles = WORKFLOW_STATE_STORE.load_json(WORKFLOW_STATE_PROFILES_KEY, {})
    loaded_snapshots = WORKFLOW_STATE_STORE.load_json(WORKFLOW_STATE_SNAPSHOTS_KEY, {})

    round_updates.clear()
    for round_id, items in (loaded_updates or {}).items():
        round_updates[str(round_id)] = [_submission_from_payload(dict(item)) for item in (items or [])]

    round_expected_agents.clear()
    round_expected_agents.update({str(round_id): list(agents or []) for round_id, agents in (loaded_expected or {}).items()})

    agent_profiles.clear()
    agent_profiles.update({str(agent_id): dict(profile or {}) for agent_id, profile in (loaded_profiles or {}).items()})

    round_state_snapshots.clear()
    round_state_snapshots.update({str(round_id): dict(snapshot or {}) for round_id, snapshot in (loaded_snapshots or {}).items()})

    for round_id, snapshot in round_state_snapshots.items():
        if str(snapshot.get("current_step")) != "round_complete":
            round_events.setdefault(round_id, asyncio.Event())

def _normalize_global_policies(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    policies = dict(DEFAULT_GLOBAL_POLICIES)
    if payload:
        policies.update(payload)
    policies["min_agents_per_round"] = max(1, int(policies.get("min_agents_per_round", 1)))
    policies["max_rounds"] = max(1, int(policies.get("max_rounds", 50)))
    policies["low_performance_accuracy"] = float(policies.get("low_performance_accuracy", 0.8))
    policies["min_update_sample_size"] = max(1, int(policies.get("min_update_sample_size", 1)))
    policies["min_update_accuracy"] = float(policies.get("min_update_accuracy", 0.5))
    policies["max_update_loss"] = float(policies.get("max_update_loss", 2.5))
    policies["min_noise_multiplier"] = float(policies.get("min_noise_multiplier", 0.0))
    policies["max_noise_multiplier"] = float(policies.get("max_noise_multiplier", 1.0))
    policies["max_accuracy_peer_delta"] = float(policies.get("max_accuracy_peer_delta", 0.35))
    policies["max_loss_peer_delta"] = float(policies.get("max_loss_peer_delta", 1.5))
    policies["require_encrypted_updates"] = bool(policies.get("require_encrypted_updates", True))
    policies["minimum_agent_reliability_score"] = float(policies.get("minimum_agent_reliability_score", 0.25))
    policies["adaptive_rejected_update_ratio"] = float(policies.get("adaptive_rejected_update_ratio", 0.25))
    required_metrics = policies.get("required_metrics") or []
    policies["required_metrics"] = [str(metric) for metric in required_metrics]
    return policies

def _ensure_agent_profile(agent_id: str) -> Dict[str, float]:
    profile = agent_profiles.setdefault(
        agent_id,
        {
            "accepted_updates": 0.0,
            "rejected_updates": 0.0,
            "reliability_score": 1.0,
            "last_accuracy": 0.0,
        },
    )
    return profile

async def _get_governance_agent(client: httpx.AsyncClient, agent_id: str) -> Dict[str, Any]:
    try:
        response = await client.get(f"{POLICY_MANAGER_URL}/governance/agent/{agent_id}", timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("Falling back to default governance rule for %s after fetch error: %s", agent_id, exc)
        return {
            "agent_id": agent_id,
            "active": True,
            "allowed_asset_types": ["CBDC"],
            "minimum_reliability_score": 0.0,
            "notes": None,
        }


async def _get_agent_runtime_snapshot(client: httpx.AsyncClient, agent_url: str) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "agent_url": agent_url,
        "reachable": False,
        "healthy": False,
        "status": {},
        "error": None,
    }

    try:
        health_response = await client.get(f"{agent_url}/health", timeout=AGENT_HEALTH_TIMEOUT_SECONDS)
        health_response.raise_for_status()
        health_payload = health_response.json() if hasattr(health_response, "json") else {}
        snapshot["reachable"] = True
        snapshot["healthy"] = str(health_payload.get("status", "")).lower() == "healthy"
    except Exception as exc:
        snapshot["error"] = f"health_check_failed: {exc}"
        return snapshot

    try:
        status_response = await client.get(f"{agent_url}/agent/status", timeout=AGENT_STATUS_TIMEOUT_SECONDS)
        status_response.raise_for_status()
        snapshot["status"] = status_response.json() if hasattr(status_response, "json") else {}
    except Exception as exc:
        snapshot["error"] = f"status_check_failed: {exc}"
        return snapshot

    return snapshot


def _runtime_snapshot_allows_selection(snapshot: Dict[str, Any], policies: Dict[str, Any]) -> Tuple[bool, str]:
    if REQUIRE_AGENT_HEALTHY and not snapshot.get("healthy", False):
        return False, "agent_unhealthy"

    if REQUIRE_AGENT_RUNTIME_STATUS and not snapshot.get("status"):
        return False, "agent_status_unavailable"

    status = snapshot.get("status") or {}
    decision = status.get("last_participation_decision") or {}
    if decision and not bool(decision.get("allowed", True)):
        return False, "agent_self_rejected_participation"

    last_metrics = status.get("last_metrics") or {}
    if "accuracy" in last_metrics:
        accuracy = float(last_metrics.get("accuracy", 0.0))
        if accuracy < float(policies.get("min_update_accuracy", 0.0)):
            return False, "historical_accuracy_below_policy"

    return True, "eligible"

async def fetch_global_policies(state: AgentState):
    logger.info("Fetching global policies from Policy Manager")
    policies = dict(DEFAULT_GLOBAL_POLICIES)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{POLICY_MANAGER_URL}/policies/global", timeout=30.0)
            response.raise_for_status()
            policies = _normalize_global_policies(response.json())
        except Exception as exc:
            logger.warning("Falling back to default policies after policy fetch error: %s", exc)
            policies = _normalize_global_policies(None)

    preferred_strategy = str(policies.get("aggregation_strategy", "FedAvg"))
    if preferred_strategy not in SUPPORTED_AGGREGATION_STRATEGIES:
        preferred_strategy = str(policies.get("fallback_aggregation_strategy", "FedAvg"))
    if preferred_strategy not in SUPPORTED_AGGREGATION_STRATEGIES:
        preferred_strategy = "FedAvg"

    state["policies"] = policies
    state["selected_strategy"] = preferred_strategy
    state["current_step"] = "policies_loaded"
    _persist_workflow_state(state["round_id"], state)
    return state

def _validate_updates(updates: List[UpdateSubmission], policies: Dict[str, Any]) -> Tuple[List[UpdateSubmission], List[Dict[str, Any]]]:
    valid_updates: List[UpdateSubmission] = []
    rejected_updates: List[Dict[str, Any]] = []
    seen_agents = set()

    min_sample_size = int(policies.get("min_update_sample_size", 1))
    min_accuracy = float(policies.get("min_update_accuracy", 0.0))
    max_loss = float(policies.get("max_update_loss", float("inf")))
    min_noise_multiplier = float(policies.get("min_noise_multiplier", 0.0))
    max_noise_multiplier = float(policies.get("max_noise_multiplier", 1.0))
    required_metrics = list(policies.get("required_metrics", []))

    for update in updates:
        if update.agent_id in seen_agents:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "duplicate_update"})
            continue
        seen_agents.add(update.agent_id)

        if not update.privacy_applied:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "privacy_not_applied"})
            continue

        if policies.get("require_encrypted_updates", True) and (not update.encryption_applied or not update.encrypted_weights):
            rejected_updates.append({"agent_id": update.agent_id, "reason": "encrypted_update_required"})
            continue

        if policies.get("require_encrypted_updates", True) and not update.encrypted_mask_share:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "secure_aggregation_mask_required"})
            continue

        if int(update.sample_size) < min_sample_size:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "sample_size_below_policy"})
            continue

        if update.noise_multiplier is not None and not (min_noise_multiplier <= float(update.noise_multiplier) <= max_noise_multiplier):
            rejected_updates.append(
                {
                    "agent_id": update.agent_id,
                    "reason": "noise_multiplier_out_of_range",
                    "noise_multiplier": float(update.noise_multiplier),
                }
            )
            continue

        missing_metrics = [metric for metric in required_metrics if metric not in (update.metrics or {})]
        if missing_metrics:
            rejected_updates.append(
                {
                    "agent_id": update.agent_id,
                    "reason": "required_metrics_missing",
                    "missing_metrics": missing_metrics,
                }
            )
            continue

        metric_values = update.metrics or {}
        range_check_failed = _check_metric_ranges(metric_values)
        if range_check_failed is not None:
            rejected_updates.append({"agent_id": update.agent_id, "reason": range_check_failed})
            continue

        consistency_check_failed = _check_metric_consistency(metric_values)
        if consistency_check_failed is not None:
            rejected_updates.append({"agent_id": update.agent_id, "reason": consistency_check_failed})
            continue

        timestamp_check_failed = _check_client_timestamp(update.client_timestamp)
        if timestamp_check_failed is not None:
            rejected_updates.append({"agent_id": update.agent_id, "reason": timestamp_check_failed})
            continue

        accuracy = float(metric_values.get("accuracy", 0.0))
        if accuracy < min_accuracy:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "accuracy_below_policy", "accuracy": accuracy})
            continue

        loss = float(metric_values.get("loss", 0.0))
        if loss > max_loss:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "loss_above_policy", "loss": loss})
            continue

        valid_updates.append(update)

    screened_updates, rejected_updates = _screen_peer_outliers(valid_updates, rejected_updates, policies)
    return _screen_model_delta_anomalies(screened_updates, rejected_updates)

def _check_metric_ranges(metrics: Dict[str, float]) -> Optional[str]:
    bounded_metrics = ("accuracy", "precision", "recall", "f1_score", "roc_auc")
    for metric_name in bounded_metrics:
        if metric_name in metrics:
            metric_value = float(metrics[metric_name])
            if metric_value < 0.0 or metric_value > 1.0:
                return f"{metric_name}_out_of_range"

    if "loss" in metrics and float(metrics["loss"]) < 0.0:
        return "loss_out_of_range"
    return None

def _check_metric_consistency(metrics: Dict[str, float]) -> Optional[str]:
    precision = metrics.get("precision")
    recall = metrics.get("recall")
    f1_score = metrics.get("f1_score")

    if precision is not None and recall is not None and f1_score is not None:
        precision = float(precision)
        recall = float(recall)
        f1_score = float(f1_score)
        if f1_score > max(precision, recall) + 1e-9:
            return "f1_inconsistent_with_precision_recall"

    return None

def _check_client_timestamp(client_timestamp: Optional[str]) -> Optional[str]:
    if not client_timestamp:
        return None

    try:
        parsed = datetime.fromisoformat(client_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "invalid_client_timestamp"

    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    age_seconds = abs((now - parsed.astimezone(timezone.utc)).total_seconds())
    if age_seconds > 3600:
        return "stale_client_timestamp"
    return None

def _screen_peer_outliers(
    valid_updates: List[UpdateSubmission],
    rejected_updates: List[Dict[str, Any]],
    policies: Dict[str, Any],
) -> Tuple[List[UpdateSubmission], List[Dict[str, Any]]]:
    if len(valid_updates) < 3:
        return valid_updates, rejected_updates

    accuracy_values = [float((update.metrics or {}).get("accuracy", 0.0)) for update in valid_updates]
    loss_values = [float((update.metrics or {}).get("loss", 0.0)) for update in valid_updates]
    median_accuracy = sorted(accuracy_values)[len(accuracy_values) // 2]
    median_loss = sorted(loss_values)[len(loss_values) // 2]
    max_accuracy_peer_delta = float(policies.get("max_accuracy_peer_delta", 0.35))
    max_loss_peer_delta = float(policies.get("max_loss_peer_delta", 1.5))

    screened_updates: List[UpdateSubmission] = []
    for update in valid_updates:
        accuracy = float((update.metrics or {}).get("accuracy", 0.0))
        loss = float((update.metrics or {}).get("loss", 0.0))
        if abs(accuracy - median_accuracy) > max_accuracy_peer_delta:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "peer_accuracy_outlier", "accuracy": accuracy})
            continue
        if abs(loss - median_loss) > max_loss_peer_delta:
            rejected_updates.append({"agent_id": update.agent_id, "reason": "peer_loss_outlier", "loss": loss})
            continue
        screened_updates.append(update)

    return screened_updates, rejected_updates


def _screen_model_delta_anomalies(
    valid_updates: List[UpdateSubmission],
    rejected_updates: List[Dict[str, Any]],
) -> Tuple[List[UpdateSubmission], List[Dict[str, Any]]]:
    if not ENABLE_MODEL_DELTA_SCREENING or len(valid_updates) < MODEL_DELTA_MIN_UPDATES:
        return valid_updates, rejected_updates

    try:
        import torch
    except Exception as exc:
        logger.info("Skipping model-delta anomaly screening because torch is unavailable: %s", exc)
        return valid_updates, rejected_updates

    decoded_vectors: List[Tuple[UpdateSubmission, Any]] = []
    expected_numel: Optional[int] = None
    for update in valid_updates:
        try:
            state_dict = torch.load(io.BytesIO(base64.b64decode(update.weights)))
            vectors = []
            for value in state_dict.values():
                if getattr(value, "is_floating_point", lambda: False)():
                    vectors.append(value.float().reshape(-1))
            if not vectors:
                rejected_updates.append({"agent_id": update.agent_id, "reason": "model_delta_payload_empty"})
                continue
            vector = torch.cat(vectors)
            if expected_numel is None:
                expected_numel = int(vector.numel())
            elif int(vector.numel()) != expected_numel:
                rejected_updates.append({"agent_id": update.agent_id, "reason": "model_delta_shape_mismatch"})
                continue
            decoded_vectors.append((update, vector))
        except Exception as exc:
            logger.warning("Failed to decode update payload for model-delta screening from %s: %s", update.agent_id, exc)
            rejected_updates.append({"agent_id": update.agent_id, "reason": "model_delta_decode_failed"})

    if len(decoded_vectors) < MODEL_DELTA_MIN_UPDATES:
        return [update for update, _vector in decoded_vectors], rejected_updates

    stacked = torch.stack([vector for _update, vector in decoded_vectors])
    centroid = stacked.mean(dim=0)
    distances = [float(torch.norm(vector - centroid).item()) for _update, vector in decoded_vectors]

    sorted_distances = sorted(distances)
    median_distance = sorted_distances[len(sorted_distances) // 2]
    abs_deviations = sorted(abs(distance - median_distance) for distance in distances)
    mad = abs_deviations[len(abs_deviations) // 2]
    distance_threshold = median_distance + MODEL_DELTA_MAD_MULTIPLIER * max(mad, 1e-9)

    screened_updates: List[UpdateSubmission] = []
    centroid_norm = float(torch.norm(centroid).item())
    for (update, vector), distance in zip(decoded_vectors, distances):
        vector_norm = float(torch.norm(vector).item())
        cosine_similarity = 1.0
        if vector_norm > 0.0 and centroid_norm > 0.0:
            cosine_similarity = float(torch.nn.functional.cosine_similarity(vector, centroid, dim=0).item())

        if distance > distance_threshold or cosine_similarity < MODEL_DELTA_MIN_COSINE_SIMILARITY:
            rejected_updates.append(
                {
                    "agent_id": update.agent_id,
                    "reason": "model_delta_anomaly_detected",
                    "delta_distance": distance,
                    "distance_threshold": distance_threshold,
                    "cosine_similarity": cosine_similarity,
                }
            )
            continue
        screened_updates.append(update)

    return screened_updates, rejected_updates

def _select_aggregation_strategy(valid_updates: List[UpdateSubmission], policies: Dict[str, Any], current_strategy: str) -> str:
    payload = [
        {
            "agent_id": update.agent_id,
            "sample_size": update.sample_size,
            "metrics": update.metrics,
        }
        for update in valid_updates
    ]
    strategy, _steps, _confidence = infer_aggregation_strategy(
        payload,
        policies,
        current_strategy,
        SUPPORTED_AGGREGATION_STRATEGIES,
    )
    return strategy


async def _select_aggregation_strategy_with_reasoning(
    valid_updates: List[UpdateSubmission],
    policies: Dict[str, Any],
    current_strategy: str,
) -> Tuple[str, List[str], str]:
    payload = [
        {
            "agent_id": update.agent_id,
            "sample_size": update.sample_size,
            "metrics": update.metrics,
        }
        for update in valid_updates
    ]
    engine = get_reasoning_engine("agentic-coordinator", "coordinator")
    decision = await engine.reason_aggregation_strategy(
        payload,
        policies,
        current_strategy,
        SUPPORTED_AGGREGATION_STRATEGIES,
    )
    return decision.aggregation_strategy, decision.reasoning_steps, decision.provider

def _update_agent_profiles(valid_updates: List[UpdateSubmission], rejected_updates: List[Dict[str, Any]]) -> None:
    for update in valid_updates:
        profile = _ensure_agent_profile(update.agent_id)
        profile["accepted_updates"] = float(profile.get("accepted_updates", 0.0)) + 1.0
        profile["last_accuracy"] = float((update.metrics or {}).get("accuracy", 0.0))
        accepted = float(profile.get("accepted_updates", 0.0))
        rejected = float(profile.get("rejected_updates", 0.0))
        total = max(1.0, accepted + rejected)
        profile["reliability_score"] = accepted / total

    for rejection in rejected_updates:
        agent_id = str(rejection.get("agent_id"))
        profile = _ensure_agent_profile(agent_id)
        profile["rejected_updates"] = float(profile.get("rejected_updates", 0.0)) + 1.0
        accepted = float(profile.get("accepted_updates", 0.0))
        rejected = float(profile.get("rejected_updates", 0.0))
        total = max(1.0, accepted + rejected)
        profile["reliability_score"] = accepted / total

def _agent_reliability(agent_id: str) -> float:
    profile = _ensure_agent_profile(agent_id)
    return float(profile.get("reliability_score", 1.0))

def _is_valid_sha256(value: Optional[str]) -> bool:
    if not value or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True

def _sha256_bytes_from_b64(payload_b64: str) -> str:
    return hashlib.sha256(payload_b64.encode("ascii")).hexdigest()

def _validate_update_commitments(update: UpdateSubmission) -> Optional[str]:
    if update.protected_payload_sha256 and not _is_valid_sha256(update.protected_payload_sha256):
        return "Invalid protected payload commitment"
    if update.encrypted_payload_sha256 and not _is_valid_sha256(update.encrypted_payload_sha256):
        return "Invalid encrypted payload commitment"
    if update.protected_payload_sha256 and update.weights:
        if _sha256_bytes_from_b64(update.weights) != update.protected_payload_sha256:
            return "Protected payload commitment mismatch"
    if update.encrypted_payload_sha256 and update.encrypted_weights:
        if _sha256_bytes_from_b64(update.encrypted_weights) != update.encrypted_payload_sha256:
            return "Encrypted payload commitment mismatch"
    return None

async def _store_secure_aggregation_mask(update: UpdateSubmission) -> None:
    if not update.encrypted_mask_share:
        return
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{POLICY_MANAGER_URL}/secure-aggregation/masks/submit",
            json={
                "round_id": update.round_id,
                "agent_id": update.agent_id,
                "encrypted_mask_share": update.encrypted_mask_share,
            },
            timeout=30.0,
        )
        response.raise_for_status()

async def _fetch_aggregate_mask(round_id: str, updates: List[UpdateSubmission], strategy: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{POLICY_MANAGER_URL}/secure-aggregation/masks/aggregate",
                json={
                    "round_id": round_id,
                    "strategy": strategy,
                    "updates": [
                        {
                            "agent_id": update.agent_id,
                            "sample_size": int(update.sample_size),
                            "reliability_score": _agent_reliability(update.agent_id),
                            "metrics": update.metrics,
                        }
                        for update in updates
                    ],
                },
                timeout=60.0,
            )
            if response.status_code == 200:
                payload = response.json()
                return str(payload.get("aggregate_mask", ""))
            else:
                logger.warning(
                    "Secure aggregation mask aggregate returned %s for round %s — proceeding without unmasking: %s",
                    response.status_code,
                    round_id,
                    response.text,
                )
                return ""
        except Exception as exc:
            logger.warning(
                "Failed to fetch aggregate mask for round %s — proceeding without unmasking: %s",
                round_id,
                exc,
            )
            return ""

def _unmask_aggregated_weights(masked_aggregate_b64: str, aggregate_mask_b64: str) -> str:
    if not aggregate_mask_b64:
        return masked_aggregate_b64
    import torch

    masked_state = torch.load(io.BytesIO(base64.b64decode(masked_aggregate_b64)))
    mask_state = torch.load(io.BytesIO(base64.b64decode(aggregate_mask_b64)))
    unmasked_state = {}
    for key, value in masked_state.items():
        mask_value = mask_state.get(key)
        if mask_value is None:
            unmasked_state[key] = value
        else:
            unmasked_state[key] = value.float() - mask_value.float()

    buffer = io.BytesIO()
    torch.save(unmasked_state, buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")

# --- Node Functions ---
async def select_agents(state: AgentState):
    logger.info(f"Selecting agents for round {state['round_id']}")
    configured_agents = [agent_url for agent_url in LOCAL_AGENT_URLS if agent_url]
    policies = _normalize_global_policies(state.get("policies"))
    selected_agents: List[str] = []

    async with httpx.AsyncClient() as client:
        for agent_url in configured_agents:
            governance = await _get_governance_agent(client, agent_url)
            profile = _ensure_agent_profile(agent_url)
            if not governance.get("active", True):
                logger.info("Skipping agent %s because governance marks it inactive", agent_url)
                continue
            allowed_asset_types = [str(asset_type) for asset_type in (governance.get("allowed_asset_types") or ["CBDC"])]
            if not any(asset_type in policies["allowed_asset_types"] for asset_type in allowed_asset_types):
                logger.info("Skipping agent %s because allowed asset types do not match current policy", agent_url)
                continue
            min_reliability = max(
                float(governance.get("minimum_reliability_score", 0.0)),
                float(policies.get("minimum_agent_reliability_score", 0.0)),
            )
            if float(profile.get("reliability_score", 1.0)) < min_reliability:
                logger.info(
                    "Skipping agent %s because reliability %.4f is below threshold %.4f",
                    agent_url,
                    float(profile.get("reliability_score", 1.0)),
                    min_reliability,
                )
                continue

            snapshot = await _get_agent_runtime_snapshot(client, agent_url)
            if snapshot.get("error") and (REQUIRE_AGENT_HEALTHY or REQUIRE_AGENT_RUNTIME_STATUS):
                logger.info("Skipping agent %s because runtime snapshot failed: %s", agent_url, snapshot.get("error"))
                continue

            runtime_allowed, runtime_reason = _runtime_snapshot_allows_selection(snapshot, policies)
            if not runtime_allowed:
                logger.info("Skipping agent %s because runtime readiness check returned %s", agent_url, runtime_reason)
                continue
            selected_agents.append(agent_url)

    engine = get_reasoning_engine("agentic-coordinator", "coordinator")
    round_decision = await engine.reason_coordinator_round(selected_agents, policies, agent_profiles)
    if round_decision.selected_agent_ids:
        selected_agents = [agent for agent in round_decision.selected_agent_ids if agent in configured_agents]
    state["reasoning_trace"] = list(round_decision.reasoning_steps)
    state["reasoning_provider"] = round_decision.provider
    strategy_hint = round_decision.aggregation_strategy_hint
    if strategy_hint in SUPPORTED_AGGREGATION_STRATEGIES:
        state["selected_strategy"] = strategy_hint

    state['active_agents'] = selected_agents
    round_expected_agents[state["round_id"]] = list(selected_agents)
    state['current_step'] = "training_triggered"
    _persist_workflow_state(state["round_id"], state)
    return state

async def trigger_training(state: AgentState):
    logger.info(f"Triggering training for agents: {state['active_agents']}")
    
    async with httpx.AsyncClient() as client:
        tasks = []
        fedprox_mu = float(state.get("policies", {}).get("fedprox_mu", 1.0))
        for agent_url in state['active_agents']:
            # Call each local agent to start its local round
            tasks.append(client.post(
                f"{agent_url}/agent/round/start",
                params={
                    "round_id": state['round_id'],
                    "agent_id": agent_url,
                    "selected_strategy": state.get("selected_strategy", "FedAvg"),
                    "fedprox_mu": fedprox_mu,
                }
            ))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.error(f"Error triggering agent {state['active_agents'][i]}: {resp}")
            elif resp.status_code == 200:
                logger.info(f"Successfully triggered agent {state['active_agents'][i]}")
            else:
                logger.error(f"Agent {state['active_agents'][i]} failed: {resp.text}")

    state['current_step'] = "waiting_for_updates"
    _persist_workflow_state(state["round_id"], state)
    return state

async def wait_for_updates(state: AgentState):
    round_id = state["round_id"]
    event = round_events.get(round_id)
    if event is None:
        event = asyncio.Event()
        round_events[round_id] = event

    try:
        await asyncio.wait_for(event.wait(), timeout=ROUND_WAIT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning(f"Timed out waiting for updates for round {round_id}")

    received = round_updates.get(round_id, [])
    state["updates_received"] = received
    state["current_step"] = "aggregating"
    _persist_workflow_state(round_id, state)
    return state

async def negotiate_weights(state: AgentState):
    logger.info("Initiating weight negotiation phase among participating agents...")
    round_id = state["round_id"]
    updates = state.get("updates_received", [])
    if not updates:
        state["negotiated_weights"] = None
        state["current_step"] = "negotiation_skipped"
        return state

    policies = _normalize_global_policies(state.get("policies"))
    valid_updates, _rejected_updates = _validate_updates(updates, policies)
    
    if not valid_updates:
        state["negotiated_weights"] = None
        state["current_step"] = "negotiation_failed"
        return state

    # Build negotiation items
    negotiation_items = []
    for u in valid_updates:
        negotiation_items.append(
            WeightNegotiationItem(
                agent_id=u.agent_id,
                sample_size=u.sample_size,
                reliability_score=_agent_reliability(u.agent_id),
                metrics=u.metrics or {}
            )
        )

    neg_request = WeightNegotiationRequest(
        round_id=round_id,
        agents=negotiation_items
    )

    proposals = {}
    async with httpx.AsyncClient() as client:
        tasks = []
        for u in valid_updates:
            tasks.append(client.post(
                f"{u.agent_id}/agent/negotiate/propose-weights",
                json=neg_request.model_dump(mode="json"),
                timeout=30.0
            ))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, resp in enumerate(responses):
            agent_id = valid_updates[i].agent_id
            if isinstance(resp, Exception):
                logger.error(f"Negotiation error from agent {agent_id}: {resp}")
            elif resp.status_code == 200:
                try:
                    neg_resp = WeightNegotiationResponse(**resp.json())
                    proposals[agent_id] = neg_resp.proposed_weights
                    logger.info(f"Received weight negotiation proposal from agent {agent_id}: {neg_resp.proposed_weights}")
                except Exception as e:
                    logger.error(f"Invalid negotiation response schema from {agent_id}: {e}")
            else:
                logger.error(f"Agent {agent_id} negotiation failed with status {resp.status_code}: {resp.text}")

    if len(proposals) < len(valid_updates) * 0.5:
        logger.warning("Fewer than 50% of valid agents participated in negotiation. Bypassing peer-negotiation consensus.")
        state["negotiated_weights"] = None
        state["current_step"] = "negotiation_fallback"
        _persist_workflow_state(round_id, state)
        return state

    # Check standard deviation of weight proposals for each agent
    agent_ids = [u.agent_id for u in valid_updates]
    consensus_reached = True
    tolerance = 0.15

    def std_dev(values):
        n = len(values)
        if n <= 1:
            return 0.0
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        return variance ** 0.5

    for target_agent in agent_ids:
        proposed_vals = []
        for _proposer, proposed_w in proposals.items():
            val = proposed_w.get(target_agent)
            if val is not None:
                proposed_vals.append(float(val))
        
        if len(proposed_vals) > 1:
            std = std_dev(proposed_vals)
            if std > tolerance:
                logger.warning(f"Disagreement detected: weight proposals for agent {target_agent} have std dev {std:.4f} > tolerance {tolerance}")
                consensus_reached = False
                break

    if consensus_reached:
        final_weights = {}
        for target_agent in agent_ids:
            vals = [float(p.get(target_agent, 0.0)) for p in proposals.values() if target_agent in p]
            final_weights[target_agent] = sum(vals) / len(vals) if vals else 1.0 / len(agent_ids)
        
        total_w = sum(final_weights.values())
        if total_w > 0:
            final_weights = {k: v / total_w for k, v in final_weights.items()}
            
        logger.info(f"Consensus weight negotiation succeeded! Final negotiated weights: {final_weights}")
        state["negotiated_weights"] = final_weights
        state["current_step"] = "negotiation_succeeded"
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{POLICY_MANAGER_URL}/governance/agent",
                    json={
                        "agent_id": "coordinator",
                        "active": True,
                        "allowed_asset_types": ["CBDC"],
                        "notes": f"Consensus weight negotiation succeeded for round {round_id} with weights: {final_weights}"
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to record governance event for successful negotiation: {e}")
    else:
        logger.warning("Weight negotiation consensus could not be reached due to diverging proposals. Falling back to central calculation.")
        state["negotiated_weights"] = None
        state["current_step"] = "negotiation_no_consensus"

    _persist_workflow_state(round_id, state)
    return state

async def aggregate_results(state: AgentState):
    logger.info("Aggregating results via Federated Model Aggregator")
    round_id = state["round_id"]
    updates = state.get("updates_received", [])
    if not updates:
        state["aggregation_complete"] = False
        state["valid_updates"] = []
        state["rejected_updates"] = []
        state["current_step"] = "round_complete"
        _persist_workflow_state(round_id, state)
        return state

    policies = _normalize_global_policies(state.get("policies"))
    valid_updates, rejected_updates = _validate_updates(updates, policies)
    state["valid_updates"] = valid_updates
    state["rejected_updates"] = rejected_updates
    
    # Track initial strategy and selection
    selected_strategy, strategy_reasoning, reasoning_provider = await _select_aggregation_strategy_with_reasoning(
        valid_updates,
        policies,
        state.get("selected_strategy", "FedAvg"),
    )
    state["selected_strategy"] = selected_strategy
    state["reasoning_provider"] = reasoning_provider
    state["reasoning_trace"] = list(state.get("reasoning_trace", [])) + list(strategy_reasoning)
    _update_agent_profiles(valid_updates, rejected_updates)

    max_aggregation_attempts = 2
    attempt = 0
    final_aggregated_weights = ""
    
    async with httpx.AsyncClient() as client:
        while attempt < max_aggregation_attempts:
            if len(valid_updates) < int(policies.get("min_agents_per_round", 1)):
                logger.warning(f"Not enough valid updates left for aggregation ({len(valid_updates)} valid updates)")
                state["aggregation_complete"] = False
                state["metrics"] = {
                    "accepted_updates": float(len(valid_updates)),
                    "rejected_updates": float(len(rejected_updates)),
                }
                break

            negotiated = state.get("negotiated_weights") or {}
            global_reference_weights = None
            if state["selected_strategy"] == "FedProxGNN":
                try:
                    latest_model_response = await client.get(f"{MODEL_REGISTRY_URL}/models/latest/weights", timeout=60.0)
                    if latest_model_response.status_code == 200:
                        latest_model_payload = latest_model_response.json()
                        global_reference_weights = latest_model_payload.get("weights")
                except Exception as exc:
                    logger.warning("FedProxGNN reference model fetch failed, falling back to peer-centroid reference: %s", exc)

            agg_payload = {
                "round_id": round_id,
                "updates": [
                    {
                        "agent_id": u.agent_id,
                        "weights": u.weights,
                        "encrypted_weights": u.encrypted_weights,
                        "sample_size": u.sample_size,
                        "metrics": u.metrics,
                        "privacy_applied": u.privacy_applied,
                        "encryption_applied": u.encryption_applied,
                        "protected_payload_sha256": u.protected_payload_sha256,
                        "encrypted_payload_sha256": u.encrypted_payload_sha256,
                        "reliability_score": _agent_reliability(u.agent_id),
                        "negotiated_weight": negotiated.get(u.agent_id),
                    }
                    for u in valid_updates
                ],
                "strategy": state["selected_strategy"],
                "noise_multiplier": 0.0,
                "global_reference_weights": global_reference_weights,
            }

            try:
                # Send the packed weights and metadata to the Federated Model Aggregator microservice
                agg_resp = await client.post(f"{FEDERATED_MODEL_AGGREGATOR_URL}/aggregate", json=agg_payload, timeout=180.0)
                if agg_resp.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Aggregation failed: {agg_resp.text}")

                # Read the response JSON dictionary from the aggregator
                agg_data = agg_resp.json()
                
                # Retrieve the shared secret mask to cancel out the Differential Privacy masks added by banks
                aggregate_mask = await _fetch_aggregate_mask(round_id, valid_updates, state["selected_strategy"])
                
                # Decrypt/Unmask the aggregated weights using our mask cancellation utility
                final_aggregated_weights = _unmask_aggregated_weights(str(agg_data.get("aggregated_weights", "")), aggregate_mask)
                state["aggregation_complete"] = bool(agg_data.get("success", False))
                
                # Save global round evaluation metrics (accuracy, loss, etc.)
                state["metrics"] = agg_data.get("global_metrics", {}) or {}
                state["metrics"]["accepted_updates"] = float(len(valid_updates))
                state["metrics"]["rejected_updates"] = float(len(rejected_updates))

                # ==========================================================
                # --- Model Rejection Check ---
                # ==========================================================
                # Non-Python/Non-ML explanation:
                # - After aggregating the weights from all banks, we test the new global model.
                # - If the new global model's accuracy is worse than the threshold (e.g. 80%) or
                #   has dropped significantly (by more than 8%) compared to the previous round,
                #   we suspect one or more bank nodes sent poisoned, bad, or corrupt data.
                # - If this happens, we:
                #   1. Identify the bank node that had the worst accuracy in this round.
                #   2. Reject and remove that bank's contributions.
                #   3. Switch our aggregation algorithm to a robust one (e.g., 'RobustMedian' which ignores outliers).
                #   4. Try aggregating again with the remaining banks' updates.
                
                # Read the minimum allowed accuracy (defaults to 80% if not configured)
                min_acc = float(policies.get("low_performance_accuracy", 0.8))
                curr_acc = float(state["metrics"].get("accuracy", 1.0))
                
                # Retrieve the previous global model accuracy from the registry to compare and check for drops
                prev_acc = 1.0
                try:
                    prev_resp = await client.get(f"{MODEL_REGISTRY_URL}/models/latest", timeout=15.0)
                    if prev_resp.status_code == 200:
                        prev_data = prev_resp.json()
                        prev_acc = float(prev_data.get("metrics", {}).get("accuracy", 1.0))
                except Exception:
                    pass

                # Check if current accuracy is below policy threshold or has dropped by more than 8%
                if (curr_acc < min_acc or (prev_acc - curr_acc) > 0.08) and len(valid_updates) > int(policies.get("min_agents_per_round", 1)):
                    # Find the update contribution that had the lowest accuracy score
                    # 'min' is a Python function that finds the smallest item. 'key' tells it how to compare items.
                    worst_update = min(valid_updates, key=lambda u: float(u.metrics.get("accuracy", 1.0)))
                    worst_agent_id = worst_update.agent_id
                    
                    logger.warning(
                        f"Model rejection triggered (attempt {attempt+1}): Global accuracy {curr_acc:.3f} degraded. "
                        f"Rejecting worst contributor: {worst_agent_id}"
                    )
                    
                    # Filter out (remove) the worst agent from our valid updates list
                    valid_updates = [u for u in valid_updates if u.agent_id != worst_agent_id]
                    state["valid_updates"] = valid_updates
                    
                    # Append the rejected agent info to our tracking list
                    rejected_updates.append({"agent_id": worst_agent_id, "reason": "model_degradation_contributor"})
                    state["rejected_updates"] = rejected_updates
                    _update_agent_profiles([], [{"agent_id": worst_agent_id, "reason": "model_degradation_contributor"}])
                    
                    # Switch to a robust strategy like 'RobustMedian' if supported, otherwise 'PerformanceWeightedFedAvg'
                    robust_strategy = "RobustMedian" if "RobustMedian" in SUPPORTED_AGGREGATION_STRATEGIES else "PerformanceWeightedFedAvg"
                    state["selected_strategy"] = robust_strategy
                    
                    # Document our autonomous choice in the reasoning trace log
                    state["reasoning_trace"].append(
                        f"Model Rejection: Global accuracy {curr_acc:.3f} degraded from previous {prev_acc:.3f} or below threshold {min_acc:.3f}. "
                        f"Rejected worst contributor {worst_agent_id}. Re-aggregating with {robust_strategy}."
                    )
                    attempt += 1
                    # 'continue' restarts the loop iteration to execute aggregation again with the new settings
                    continue
                else:
                    # Model passed validation or we cannot perform further re-aggregation (minimum agent limit reached)
                    # 'break' exits the loop immediately
                    break

            except HTTPException:
                raise
            except Exception as agg_exc:
                logger.error(
                    "Unexpected error during aggregation for round %s — round marked incomplete: %s",
                    round_id,
                    agg_exc,
                )
                state["aggregation_complete"] = False
                state.setdefault("metrics", {})["aggregation_error"] = 1.0
                break

        # Register final model if aggregation was successful
        if state.get("aggregation_complete") and final_aggregated_weights:
            try:
                reg_response = await client.post(
                    f"{MODEL_REGISTRY_URL}/models/register",
                    json={
                        "metrics": state["metrics"],
                        "artifact_path": "",
                        "is_global": True,
                        "weights": final_aggregated_weights,
                    },
                    timeout=60.0,
                )
                if reg_response.status_code == 200:
                    reg_payload = reg_response.json()
                    registered_version_id = reg_payload.get("version_id")
                    state["metrics"]["registered_version_id"] = 1.0
                    state["metrics"]["registry_registered"] = 1.0
                    logger.info(
                        "Successfully registered aggregated model with version_id=%s for round %s",
                        registered_version_id,
                        round_id,
                    )
                else:
                    logger.warning(
                        "Model registry registration returned non-200 status %s for round %s: %s",
                        reg_response.status_code,
                        round_id,
                        reg_response.text,
                    )
            except Exception as e:
                logger.warning(f"Model registry registration failed: {e}")

        # Update budget spending policies
        for u in valid_updates:
            try:
                await client.post(
                    f"{POLICY_MANAGER_URL}/policies/budget/update",
                    json={"agent_id": u.agent_id, "epsilon_spent": 0.1, "delta_spent": 0.0},
                    timeout=30.0,
                )
            except Exception as e:
                logger.warning(f"Policy budget update failed for {u.agent_id}: {e}")

    state["current_step"] = "round_complete"
    _persist_workflow_state(round_id, state)
    return state

# --- Graph Construction ---
workflow = StateGraph(AgentState)
workflow.add_node("fetch_global_policies", fetch_global_policies)
workflow.add_node("select_agents", select_agents)
workflow.add_node("trigger_training", trigger_training)
workflow.add_node("wait_for_updates", wait_for_updates)
workflow.add_node("negotiate_weights", negotiate_weights)
workflow.add_node("aggregate_results", aggregate_results)

workflow.set_entry_point("fetch_global_policies")
workflow.add_edge("fetch_global_policies", "select_agents")
workflow.add_edge("select_agents", "trigger_training")
workflow.add_edge("trigger_training", "wait_for_updates")
workflow.add_edge("wait_for_updates", "negotiate_weights")
workflow.add_edge("negotiate_weights", "aggregate_results")
workflow.add_edge("aggregate_results", END)

app_graph = workflow.compile()

# --- FastAPI Setup ---
@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    _load_persisted_workflow_state()
    yield


app = FastAPI(title="Agentic Coordinator Service", lifespan=app_lifespan)

@app.get("/health")
async def health_check():
    """
    BUSINESS PURPOSE / REASON: Checked by monitoring servers to verify that the Coordinator
    is online and healthy.
    """
    return {"status": "healthy"}

@app.post("/updates/submit", response_model=SubmissionAck)
async def submit_update(update: UpdateSubmission):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the individual bank nodes after they
    finish training. It accepts their masked GNN weights, saves them in Redis/memory, and notifies
    the active round wait-task. The business goal is to receive all bank updates securely.
    """
    if not update.privacy_applied:
        raise HTTPException(status_code=400, detail="Protected model update required before submission")
    if not update.weights:
        raise HTTPException(status_code=400, detail="Protected weights payload is required")
    if update.encryption_applied and not update.encrypted_weights:
        raise HTTPException(status_code=400, detail="Encrypted payload metadata is required when encryption is declared")
    if update.encryption_applied and not update.encrypted_mask_share:
        raise HTTPException(status_code=400, detail="Secure aggregation mask share is required when encryption is declared")
    commitment_error = _validate_update_commitments(update)
    if commitment_error:
        raise HTTPException(status_code=400, detail=commitment_error)
    try:
        await _store_secure_aggregation_mask(update)
    except Exception as exc:
        logger.error("Failed to store secure aggregation mask share for %s: %s", update.agent_id, exc)
        raise HTTPException(status_code=502, detail="Failed to store secure aggregation mask share") from exc

    updates = round_updates.setdefault(update.round_id, [])
    updates.append(update)
    _persist_workflow_state(update.round_id)

    expected = round_expected_agents.get(update.round_id, [])
    if expected and len({u.agent_id for u in updates}) >= len(expected):
        event = round_events.get(update.round_id)
        if event is None:
            event = asyncio.Event()
            round_events[update.round_id] = event
        event.set()
        _persist_workflow_state(update.round_id)
        return SubmissionAck(accepted=True, message="Update received (round complete)")

    _persist_workflow_state(update.round_id)
    return SubmissionAck(accepted=True, message="Update received")

@app.post("/rounds/start")
async def start_round(round_id: str):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the orchestration script or dashboard
    to trigger a collaborative training round. It kicks off the agentic LangGraph workflow,
    from policy checking to aggregation and final model registry saving.
    """
    logger.info(f"Starting federated round: {round_id}")
    round_updates[round_id] = []
    round_expected_agents[round_id] = []
    round_events[round_id] = asyncio.Event()
    initial_state: AgentState = {
        "round_id": round_id,
        "active_agents": [],
        "updates_received": [],
        "valid_updates": [],
        "rejected_updates": [],
        "aggregation_complete": False,
        "metrics": {},
        "policies": {},
        "selected_strategy": "FedAvg",
        "current_step": "init",
        "negotiated_weights": None,
        "reasoning_trace": [],
        "reasoning_provider": "expert-inference",
    }
    _persist_workflow_state(round_id, initial_state)
    
    # Run the agentic workflow
    final_state = await app_graph.ainvoke(initial_state)
    if isinstance(final_state, dict):
        round_expected_agents[round_id] = list(final_state.get("active_agents", []) or [])
        _persist_workflow_state(round_id, final_state)
    return {"status": "success", "final_state": final_state}

@app.post("/consensus/propose-fraud-pattern")
async def propose_fraud_pattern(proposal: FraudPatternProposal):
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by bank nodes to propose a new GNN fraud taxonomy
    rule (e.g. flagging self-transfers or high-velocity accounts). It initiates a network-wide poll across
    all banks, counts votes, and updates the Policy Manager upon consensus.
    """
    logger.info(f"Consensus proposal received: {proposal.proposal_id} ({proposal.pattern_name}) from proposer {proposal.proposer_id}")
    active_agents = LOCAL_AGENT_URLS
    
    votes: List[ConsensusVote] = []
    async with httpx.AsyncClient() as client:
        tasks = []
        for agent_url in active_agents:
            if not agent_url:
                continue
            tasks.append(client.post(
                f"{agent_url}/agent/consensus/evaluate-pattern",
                json=proposal.model_dump(mode="json"),
                timeout=30.0
            ))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, resp in enumerate(responses):
            agent_url = active_agents[i]
            if isinstance(resp, Exception):
                logger.error(f"Failed to get consensus vote from agent {agent_url}: {resp}")
            elif resp.status_code == 200:
                try:
                    vote_resp = ConsensusVote(**resp.json())
                    votes.append(vote_resp)
                    logger.info(f"Agent {agent_url} voted: {vote_resp.vote} (Reason: {vote_resp.reason})")
                except Exception as e:
                    logger.error(f"Invalid vote response from agent {agent_url}: {e}")
            else:
                logger.error(f"Agent {agent_url} vote failed with status {resp.status_code}: {resp.text}")

    if not votes:
        raise HTTPException(status_code=502, detail="No active agents could evaluate the fraud pattern proposal")

    approvals = sum(1 for v in votes if v.vote == "APPROVE")
    rejections = sum(1 for v in votes if v.vote == "REJECT")
    consensus_reached = approvals > (len(votes) / 2)

    logger.info(f"Consensus summary for proposal {proposal.proposal_id}: Approvals={approvals}, Rejections={rejections}, Reached={consensus_reached}")

    if consensus_reached:
        async with httpx.AsyncClient() as client:
            try:
                policy_resp = await client.get(f"{POLICY_MANAGER_URL}/policies/global", timeout=30.0)
                policy_resp.raise_for_status()
                current_policies = policy_resp.json()
            except Exception as e:
                logger.warning(f"Failed to retrieve current policies, using empty defaults: {e}")
                current_policies = {}

            taxonomy = current_policies.get("fraud_taxonomy", [])
            new_pattern = {
                "proposal_id": proposal.proposal_id,
                "pattern_name": proposal.pattern_name,
                "feature_indicators": proposal.feature_indicators,
                "rationale": proposal.rationale,
                "proposer_id": proposal.proposer_id,
                "approved_at": datetime.now(timezone.utc).isoformat()
            }
            taxonomy = [p for p in taxonomy if p.get("proposal_id") != proposal.proposal_id]
            taxonomy.append(new_pattern)
            current_policies["fraud_taxonomy"] = taxonomy

            try:
                update_resp = await client.post(
                    f"{POLICY_MANAGER_URL}/policies/global",
                    json={
                        "policies": current_policies,
                        "updated_by": f"consensus-{proposal.proposal_id[:8]}"
                    },
                    timeout=30.0
                )
                update_resp.raise_for_status()
                logger.info("Successfully updated global fraud taxonomy in Policy Manager")
            except Exception as e:
                logger.error(f"Failed to update policies in Policy Manager: {e}")
                raise HTTPException(status_code=502, detail="Failed to store approved fraud taxonomy update")

        return {
            "status": "approved",
            "consensus_reached": True,
            "approvals": approvals,
            "rejections": rejections,
            "votes": [v.model_dump(mode="json") for v in votes],
            "proposal": proposal.model_dump(mode="json")
        }
    else:
        return {
            "status": "rejected",
            "consensus_reached": False,
            "approvals": approvals,
            "rejections": rejections,
            "votes": [v.model_dump(mode="json") for v in votes],
            "proposal": proposal.model_dump(mode="json")
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
