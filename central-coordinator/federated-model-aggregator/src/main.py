"""
================================================================================
FEDERATED MODEL AGGREGATOR - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Federated Model Aggregator as the "mixer" or "blender" of the system.
Its primary job is to combine the learning results (model updates) from all
participating banks into a single, unified "Global Model."

Since each bank has trained its GNN model locally on its own private transaction
graph, they send their results back as encrypted lists of numbers (weights). 

To blend these weights properly, we use different algorithms (strategies):
1. FedAvg: The simplest approach — we treat all banks equally and average their numbers.
2. WeightedFedAvg: We give larger banks (who have more transactions) a stronger vote
   in the average, since they have seen more data.
3. PerformanceWeightedFedAvg: We reward banks that have higher accuracy or F1 scores
   by letting their model updates count more in the blend.
4. FedProxGNN: We apply a penalty for models that have strayed too far from the previous
   round's starting point, ensuring training remains stable.
5. RobustMedian: Instead of averaging, we find the middle value. This acts as a shield
   against malicious uploads — if one bank sends extremely corrupted data, it will be
   discarded as an outlier.
================================================================================
"""
import logging
import io
import base64
import hashlib
import math
import os
from typing import Dict, List, Optional

import torch
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _resolve_transport_cipher() -> Fernet:
    explicit_key = os.getenv("PRIVACY_FERNET_KEY")
    if explicit_key:
        return Fernet(explicit_key.encode("ascii"))

    seed = os.getenv("PRIVACY_KEY_SEED", "development-only-shared-key")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(derived_key)

TRANSPORT_CIPHER = _resolve_transport_cipher()
SUPPORTED_AGGREGATION_STRATEGIES = {
    "FedAvg",
    "WeightedFedAvg",
    "PerformanceWeightedFedAvg",
    "AdaptiveFedAvg",
    "FedProxGNN",
    "FedGraph",
    "RobustMedian",
}
FEDPROX_MU = float(os.getenv("FEDPROX_MU", "1.0"))


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


def _aggregation_weight(update: "AggregationItem", strategy: str) -> float:
    base_weight = float(max(0, int(update.sample_size)))
    reliability_weight = max(0.1, float(update.reliability_score))
    quality_weight = _metric_quality_score(update.metrics or {})

    if strategy == "WeightedFedAvg":
        return base_weight * reliability_weight
    if strategy == "PerformanceWeightedFedAvg":
        return base_weight * quality_weight
    if strategy == "AdaptiveFedAvg":
        return base_weight * reliability_weight * quality_weight
    return base_weight


def _scalar_value(value) -> float:
    if hasattr(value, "item"):
        try:
            return float(value.item())
        except Exception:
            pass
    if hasattr(value, "value"):
        return float(value.value)
    return float(value)


def _scalar_tensor_like(example, value: float):
    tensor_type = type(example)
    try:
        return tensor_type(value)
    except Exception:
        return value


def _mean_abs_tensor_delta(left, right) -> float:
    try:
        delta = (left.float() - right.float()).abs()
        if hasattr(delta, "mean"):
            return float(delta.mean().item())
        return abs(_scalar_value(delta))
    except Exception:
        return abs(_scalar_value(left) - _scalar_value(right))


def _weighted_average_state_dicts(state_dicts: List[Dict[str, torch.Tensor]], aggregation_weights: List[float]) -> Dict[str, torch.Tensor]:
    if not state_dicts:
        raise HTTPException(status_code=400, detail="No model updates provided")

    total_weight = float(sum(aggregation_weights))
    if total_weight <= 0:
        raise HTTPException(status_code=400, detail="Invalid aggregation weights")

    base_state = state_dicts[0]
    global_state = {key: torch.zeros_like(val).float() for key, val in base_state.items()}
    for client_state, weight in zip(state_dicts, aggregation_weights):
        normalized_weight = float(weight) / total_weight
        for key in global_state:
            global_state[key] += client_state[key].float() * normalized_weight
    return global_state


def _state_distance(left_state: Dict[str, torch.Tensor], right_state: Dict[str, torch.Tensor]) -> float:
    component_distances: List[float] = []
    for key, left_value in left_state.items():
        right_value = right_state.get(key)
        if right_value is None:
            continue
        if torch.is_floating_point(left_value):
            component_distances.append(_mean_abs_tensor_delta(left_value, right_value))
    if not component_distances:
        return 0.0
    return float(sum(component_distances) / len(component_distances))


def _median_tensor(tensors: List[torch.Tensor]):
    if not tensors:
        raise HTTPException(status_code=400, detail="No tensors provided for robust aggregation")

    first_tensor = tensors[0]
    if not hasattr(torch, "stack") or hasattr(first_tensor, "value"):
        sorted_values = sorted(_scalar_value(tensor) for tensor in tensors)
        midpoint = len(sorted_values) // 2
        if len(sorted_values) % 2 == 1:
            median_value = sorted_values[midpoint]
        else:
            median_value = (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2.0
        return _scalar_tensor_like(first_tensor, median_value)

    stacked = torch.stack([tensor.float() for tensor in tensors], dim=0)
    median_result = torch.median(stacked, dim=0)
    return median_result.values if hasattr(median_result, "values") else median_result[0]


def _coordinate_median_state_dict(state_dicts: List[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
    base_state = state_dicts[0]
    robust_state: Dict[str, torch.Tensor] = {}
    for key, base_value in base_state.items():
        tensor_group = [state[key] for state in state_dicts]
        if torch.is_floating_point(base_value):
            robust_state[key] = _median_tensor(tensor_group)
        else:
            robust_state[key] = tensor_group[0]
    return robust_state


def _graph_structure_score(update: "AggregationItem") -> float:
    metrics = update.metrics or {}
    graph_node_count = max(float(metrics.get("graph_node_count", 0.0)), float(update.sample_size))
    graph_edge_count = max(0.0, float(metrics.get("graph_edge_count", 0.0)))
    labeled_ratio = _clamp(float(metrics.get("labeled_ratio", 0.0)), 0.0, 1.0)
    avg_degree = max(0.0, float(metrics.get("avg_degree", 0.0)))

    density_metric = float(metrics.get("graph_density", 0.0))
    if density_metric <= 0.0 and graph_node_count > 1.0:
        density_metric = graph_edge_count / max(1.0, graph_node_count * (graph_node_count - 1.0))

    density_signal = _clamp(density_metric * 50.0, 0.0, 1.0)
    degree_signal = _clamp(avg_degree / 8.0, 0.0, 1.0)
    scale_signal = _clamp(math.log1p(graph_node_count) / 8.0, 0.0, 1.0)
    coverage_signal = labeled_ratio if labeled_ratio > 0.0 else _clamp(float(update.sample_size) / max(graph_node_count, 1.0), 0.0, 1.0)

    score = (
        0.4 * coverage_signal
        + 0.25 * density_signal
        + 0.2 * degree_signal
        + 0.15 * scale_signal
    )
    return max(0.1, score)


def _serialize_state_dict(state_dict: Dict[str, torch.Tensor]) -> bytes:
    buffer = io.BytesIO()
    torch.save(state_dict, buffer)
    return buffer.getvalue()


def _deserialize_state_dict(payload: bytes) -> Dict[str, torch.Tensor]:
    return torch.load(io.BytesIO(payload))


def _resolve_strategy_aggregation(
    strategy: str,
    state_dicts: List[Dict[str, torch.Tensor]],
    updates: List["AggregationItem"],
    reference_state: Optional[Dict[str, torch.Tensor]] = None,
) -> tuple[Dict[str, torch.Tensor], List[float]]:
    if strategy == "RobustMedian":
        return _coordinate_median_state_dict(state_dicts), [float(max(1, int(update.sample_size))) for update in updates]

    if strategy == "FedGraph":
        graph_weights = [
            float(max(0, int(update.sample_size)))
            * max(0.1, float(update.reliability_score))
            * _metric_quality_score(update.metrics or {})
            * _graph_structure_score(update)
            for update in updates
        ]
        return _weighted_average_state_dicts(state_dicts, graph_weights), graph_weights

    if strategy == "FedProxGNN":
        base_weights = [
            float(max(0, int(update.sample_size))) * max(0.1, float(update.reliability_score))
            for update in updates
        ]
        if reference_state is None:
            reference_state = _weighted_average_state_dicts(state_dicts, base_weights)

        fedprox_weights: List[float] = []
        for state_dict, update, base_weight in zip(state_dicts, updates, base_weights):
            quality_weight = _metric_quality_score(update.metrics or {})
            drift_penalty = 1.0 / (1.0 + FEDPROX_MU * _state_distance(state_dict, reference_state))
            fedprox_weights.append(max(0.1, base_weight * quality_weight * drift_penalty))
        return _weighted_average_state_dicts(state_dicts, fedprox_weights), fedprox_weights

    aggregation_weights = [_aggregation_weight(update, strategy) for update in updates]
    return _weighted_average_state_dicts(state_dicts, aggregation_weights), aggregation_weights

class FederatedModelAggregator:
    @staticmethod
    def federated_averaging(model_updates: List[bytes], aggregation_weights: List[float]) -> bytes:
        """
        Performs Federated Averaging (FedAvg) on a list of model updates.
        Updates are expected to be serialized PyTorch state_dicts.
        """
        if not model_updates:
            return b""

        state_dicts = [_deserialize_state_dict(update_bytes) for update_bytes in model_updates]
        global_state = _weighted_average_state_dicts(state_dicts, aggregation_weights)
        return _serialize_state_dict(global_state)

    @staticmethod
    def add_dp_noise(state_dict: Dict[str, torch.Tensor], noise_multiplier: float) -> Dict[str, torch.Tensor]:
        if noise_multiplier <= 0:
            return state_dict
        noisy = {}
        for k, v in state_dict.items():
            if torch.is_floating_point(v):
                noisy[k] = v + (torch.randn_like(v) * noise_multiplier)
            else:
                noisy[k] = v
        return noisy

class AggregationItem(BaseModel):
    agent_id: str
    weights: str
    encrypted_weights: Optional[str] = None
    protected_payload_sha256: Optional[str] = None
    encrypted_payload_sha256: Optional[str] = None
    sample_size: int
    reliability_score: float = 1.0
    metrics: Dict[str, float] = {}
    privacy_applied: bool = False
    encryption_applied: bool = False
    negotiated_weight: Optional[float] = None

class AggregateRequest(BaseModel):
    round_id: str
    updates: List[AggregationItem]
    strategy: str = "FedAvg"
    noise_multiplier: float = 0.0
    global_reference_weights: Optional[str] = None

class AggregateResponse(BaseModel):
    success: bool
    aggregated_weights: str
    global_metrics: Dict[str, float]

def _resolve_update_payload(update: AggregationItem) -> bytes:
    if not update.privacy_applied:
        raise HTTPException(status_code=400, detail=f"Update from {update.agent_id} is missing privacy protection")

    if update.encryption_applied:
        if not update.encrypted_weights:
            raise HTTPException(status_code=400, detail=f"Encrypted payload missing for {update.agent_id}")
        try:
            encrypted_payload = base64.b64decode(update.encrypted_weights)
            if update.encrypted_payload_sha256:
                actual_encrypted_hash = hashlib.sha256(update.encrypted_weights.encode("ascii")).hexdigest()
                if actual_encrypted_hash != update.encrypted_payload_sha256:
                    raise HTTPException(status_code=400, detail=f"Encrypted commitment mismatch for {update.agent_id}")
            decrypted_payload = TRANSPORT_CIPHER.decrypt(encrypted_payload)
            if update.protected_payload_sha256:
                protected_payload_b64 = base64.b64encode(decrypted_payload).decode("ascii")
                actual_protected_hash = hashlib.sha256(protected_payload_b64.encode("ascii")).hexdigest()
                if actual_protected_hash != update.protected_payload_sha256:
                    raise HTTPException(status_code=400, detail=f"Protected commitment mismatch for {update.agent_id}")
            return decrypted_payload
        except InvalidToken as exc:
            raise HTTPException(status_code=400, detail=f"Unable to decrypt payload for {update.agent_id}") from exc

    if not update.weights:
        raise HTTPException(status_code=400, detail=f"Protected weights missing for {update.agent_id}")
    if update.protected_payload_sha256:
        actual_protected_hash = hashlib.sha256(update.weights.encode("ascii")).hexdigest()
        if actual_protected_hash != update.protected_payload_sha256:
            raise HTTPException(status_code=400, detail=f"Protected commitment mismatch for {update.agent_id}")
    return base64.b64decode(update.weights)

app = FastAPI(title="Federated Model Aggregator Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/aggregate")
async def aggregate(request: AggregateRequest) -> AggregateResponse:
    try:
        if not request.updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        model_updates = [_resolve_update_payload(u) for u in request.updates]
        state_dicts = [_deserialize_state_dict(payload) for payload in model_updates]
        sample_sizes = [max(0, int(u.sample_size)) for u in request.updates]
        if sum(sample_sizes) == 0:
            raise HTTPException(status_code=400, detail="Invalid sample sizes")

        if request.strategy not in SUPPORTED_AGGREGATION_STRATEGIES:
            raise HTTPException(status_code=400, detail=f"Unsupported aggregation strategy: {request.strategy}")

        reference_state = None
        if request.global_reference_weights:
            reference_state = _deserialize_state_dict(base64.b64decode(request.global_reference_weights))

        if any(u.negotiated_weight is not None for u in request.updates):
            aggregation_weights = [
                float(u.negotiated_weight if u.negotiated_weight is not None else 0.0)
                for u in request.updates
            ]
            aggregated_state = _weighted_average_state_dicts(state_dicts, aggregation_weights)
        else:
            aggregated_state, aggregation_weights = _resolve_strategy_aggregation(
                request.strategy,
                state_dicts,
                request.updates,
                reference_state=reference_state,
            )

        aggregated_bytes = _serialize_state_dict(aggregated_state)
        if request.noise_multiplier and request.noise_multiplier > 0:
            noisy = FederatedModelAggregator.add_dp_noise(aggregated_state, float(request.noise_multiplier))
            aggregated_bytes = _serialize_state_dict(noisy)

        global_metrics: Dict[str, float] = {}
        metric_keys = set()
        for u in request.updates:
            metric_keys.update((u.metrics or {}).keys())

        total_weight = float(sum(aggregation_weights))
        for key in metric_keys:
            acc = 0.0
            for u, weight in zip(request.updates, aggregation_weights):
                val = float((u.metrics or {}).get(key, 0.0))
                acc += val * (weight / total_weight)
            global_metrics[key] = acc

        return AggregateResponse(
            success=True,
            aggregated_weights=base64.b64encode(aggregated_bytes).decode("ascii"),
            global_metrics=global_metrics,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aggregation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
