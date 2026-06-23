import logging
import io
import base64
import hashlib
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

class FederatedModelAggregator:
    @staticmethod
    def federated_averaging(model_updates: List[bytes], aggregation_weights: List[float]) -> bytes:
        """
        Performs Federated Averaging (FedAvg) on a list of model updates.
        Updates are expected to be serialized PyTorch state_dicts.
        """
        if not model_updates:
            return b""
        
        total_weight = sum(aggregation_weights)
        if total_weight <= 0:
            raise HTTPException(status_code=400, detail="Invalid aggregation weights")
        # Load the first update as the base
        base_update = torch.load(io.BytesIO(model_updates[0]))
        
        # Initialize the global state dict with zero weights
        global_state = {key: torch.zeros_like(val).float() for key, val in base_update.items()}
        
        # Aggregate weights
        for i, update_bytes in enumerate(model_updates):
            client_state = torch.load(io.BytesIO(update_bytes))
            weight = aggregation_weights[i] / total_weight
            
            for key in global_state:
                global_state[key] += client_state[key].float() * weight
        
        # Serialize global state
        buffer = io.BytesIO()
        torch.save(global_state, buffer)
        return buffer.getvalue()

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
        sample_sizes = [max(0, int(u.sample_size)) for u in request.updates]
        if sum(sample_sizes) == 0:
            raise HTTPException(status_code=400, detail="Invalid sample sizes")

        if request.strategy not in {"FedAvg", "WeightedFedAvg"}:
            raise HTTPException(status_code=400, detail=f"Unsupported aggregation strategy: {request.strategy}")

        if any(u.negotiated_weight is not None for u in request.updates):
            aggregation_weights = [
                float(u.negotiated_weight if u.negotiated_weight is not None else 0.0)
                for u in request.updates
            ]
        else:
            aggregation_weights = [float(size) for size in sample_sizes]
            if request.strategy == "WeightedFedAvg":
                aggregation_weights = [
                    float(size) * max(0.1, float(update.reliability_score))
                    for update, size in zip(request.updates, sample_sizes)
                ]

        aggregated_bytes = FederatedModelAggregator.federated_averaging(model_updates, aggregation_weights)
        if request.noise_multiplier and request.noise_multiplier > 0:
            state = torch.load(io.BytesIO(aggregated_bytes))
            noisy = FederatedModelAggregator.add_dp_noise(state, float(request.noise_multiplier))
            out = io.BytesIO()
            torch.save(noisy, out)
            aggregated_bytes = out.getvalue()

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
