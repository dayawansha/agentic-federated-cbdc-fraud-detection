import logging
import os
import sys
import hashlib
import base64
import io
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple, TypedDict
from langgraph.graph import StateGraph, END
import asyncio
import httpx
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.schemas.models import (
    WeightNegotiationRequest,
    WeightNegotiationItem,
    WeightNegotiationResponse,
    FraudPatternProposal,
    ConsensusVote,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configuration
LOCAL_AGENT_URLS = os.getenv("LOCAL_AGENT_URLS", "http://localhost:9001").split(",")
FEDERATED_MODEL_AGGREGATOR_URL = os.getenv("FEDERATED_MODEL_AGGREGATOR_URL", "http://localhost:8002")
POLICY_MANAGER_URL = os.getenv("POLICY_MANAGER_URL", "http://localhost:8003")
MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://localhost:8004")
ROUND_WAIT_SECONDS = float(os.getenv("ROUND_WAIT_SECONDS", "300"))

class UpdateSubmission(BaseModel):
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
    accepted: bool
    message: str

round_updates: Dict[str, List[UpdateSubmission]] = {}
round_expected_agents: Dict[str, List[str]] = {}
round_events: Dict[str, asyncio.Event] = {}
agent_profiles: Dict[str, Dict[str, float]] = {}
SUPPORTED_AGGREGATION_STRATEGIES = {"FedAvg", "WeightedFedAvg"}
DEFAULT_GLOBAL_POLICIES: Dict[str, Any] = {
    "min_agents_per_round": 1,
    "max_rounds": 50,
    "aggregation_strategy": "FedAvg",
    "fallback_aggregation_strategy": "WeightedFedAvg",
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
    "adaptive_strategy_on_rejection": "WeightedFedAvg",
}

# --- LangGraph State Definition ---
class AgentState(TypedDict):
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

    return _screen_peer_outliers(valid_updates, rejected_updates, policies)

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

def _select_aggregation_strategy(valid_updates: List[UpdateSubmission], policies: Dict[str, Any], current_strategy: str) -> str:
    if not valid_updates:
        return current_strategy

    avg_accuracy = sum(float((update.metrics or {}).get("accuracy", 0.0)) for update in valid_updates) / len(valid_updates)
    rejected_ratio = 0.0
    total_updates = len(valid_updates)
    if total_updates > 0:
        low_quality_count = sum(1 for update in valid_updates if float((update.metrics or {}).get("accuracy", 0.0)) < float(policies.get("low_performance_accuracy", 0.0)))
        rejected_ratio = low_quality_count / total_updates
    fallback = str(policies.get("fallback_aggregation_strategy", current_strategy))
    if avg_accuracy < float(policies.get("low_performance_accuracy", 0.0)) and fallback in SUPPORTED_AGGREGATION_STRATEGIES:
        return fallback
    adaptive_strategy = str(policies.get("adaptive_strategy_on_rejection", fallback))
    if rejected_ratio >= float(policies.get("adaptive_rejected_update_ratio", 1.0)) and adaptive_strategy in SUPPORTED_AGGREGATION_STRATEGIES:
        return adaptive_strategy
    return current_strategy

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
                    }
                    for update in updates
                ],
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("aggregate_mask", ""))

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
                continue
            allowed_asset_types = [str(asset_type) for asset_type in (governance.get("allowed_asset_types") or ["CBDC"])]
            if not any(asset_type in policies["allowed_asset_types"] for asset_type in allowed_asset_types):
                continue
            min_reliability = max(
                float(governance.get("minimum_reliability_score", 0.0)),
                float(policies.get("minimum_agent_reliability_score", 0.0)),
            )
            if float(profile.get("reliability_score", 1.0)) < min_reliability:
                continue
            selected_agents.append(agent_url)

    state['active_agents'] = selected_agents or configured_agents
    state['current_step'] = "training_triggered"
    return state

async def trigger_training(state: AgentState):
    logger.info(f"Triggering training for agents: {state['active_agents']}")
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for agent_url in state['active_agents']:
            # Call each local agent to start its local round
            tasks.append(client.post(
                f"{agent_url}/agent/round/start",
                params={"round_id": state['round_id'], "agent_id": agent_url}
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
    valid_updates, rejected_updates = _validate_updates(updates, policies)
    
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
        for proposer, proposed_w in proposals.items():
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
        return state

    policies = _normalize_global_policies(state.get("policies"))
    valid_updates, rejected_updates = _validate_updates(updates, policies)
    state["valid_updates"] = valid_updates
    state["rejected_updates"] = rejected_updates
    state["selected_strategy"] = _select_aggregation_strategy(valid_updates, policies, state.get("selected_strategy", "FedAvg"))
    _update_agent_profiles(valid_updates, rejected_updates)

    if len(valid_updates) < int(policies.get("min_agents_per_round", 1)):
        state["aggregation_complete"] = False
        state["metrics"] = {
            "accepted_updates": float(len(valid_updates)),
            "rejected_updates": float(len(rejected_updates)),
        }
        state["current_step"] = "round_complete"
        return state

    async with httpx.AsyncClient() as client:
        negotiated = state.get("negotiated_weights") or {}
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
        }
        agg_resp = await client.post(f"{FEDERATED_MODEL_AGGREGATOR_URL}/aggregate", json=agg_payload, timeout=180.0)
        if agg_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Aggregation failed: {agg_resp.text}")

        agg_data = agg_resp.json()
        aggregate_mask = await _fetch_aggregate_mask(round_id, valid_updates, state["selected_strategy"])
        final_aggregated_weights = _unmask_aggregated_weights(str(agg_data.get("aggregated_weights", "")), aggregate_mask)
        state["aggregation_complete"] = bool(agg_data.get("success", False))
        state["metrics"] = agg_data.get("global_metrics", {}) or {}
        state["metrics"]["accepted_updates"] = float(len(valid_updates))
        state["metrics"]["rejected_updates"] = float(len(rejected_updates))

        try:
            await client.post(
                f"{MODEL_REGISTRY_URL}/models/register",
                json={
                    "metrics": state["metrics"],
                    "artifact_path": "",
                    "is_global": True,
                    "weights": final_aggregated_weights,
                },
                timeout=60.0,
            )
        except Exception as e:
            logger.warning(f"Model registry registration failed: {e}")

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
app = FastAPI(title="Agentic Coordinator Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/updates/submit", response_model=SubmissionAck)
async def submit_update(update: UpdateSubmission):
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

    expected = round_expected_agents.get(update.round_id, [])
    if expected and len({u.agent_id for u in updates}) >= len(expected):
        event = round_events.get(update.round_id)
        if event is None:
            event = asyncio.Event()
            round_events[update.round_id] = event
        event.set()
        return SubmissionAck(accepted=True, message="Update received (round complete)")

    return SubmissionAck(accepted=True, message="Update received")

@app.post("/rounds/start")
async def start_round(round_id: str):
    logger.info(f"Starting federated round: {round_id}")
    round_updates[round_id] = []
    round_expected_agents[round_id] = LOCAL_AGENT_URLS
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
        "negotiated_weights": None
    }
    
    # Run the agentic workflow
    final_state = await app_graph.ainvoke(initial_state)
    return {"status": "success", "final_state": final_state}

@app.post("/consensus/propose-fraud-pattern")
async def propose_fraud_pattern(proposal: FraudPatternProposal):
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
