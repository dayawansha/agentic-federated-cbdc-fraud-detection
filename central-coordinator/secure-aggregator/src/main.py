import logging
import io
from typing import Dict, List, Optional

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecureAggregator:
    @staticmethod
    def federated_averaging(model_updates: List[bytes], sample_sizes: List[int]) -> bytes:
        """
        Performs Federated Averaging (FedAvg) on a list of model updates.
        Updates are expected to be serialized PyTorch state_dicts.
        """
        if not model_updates:
            return b""
        
        total_samples = sum(sample_sizes)
        # Load the first update as the base
        base_update = torch.load(io.BytesIO(model_updates[0]))
        
        # Initialize the global state dict with zero weights
        global_state = {key: torch.zeros_like(val).float() for key, val in base_update.items()}
        
        # Aggregate weights
        for i, update_bytes in enumerate(model_updates):
            client_state = torch.load(io.BytesIO(update_bytes))
            weight = sample_sizes[i] / total_samples
            
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
    weights: bytes
    sample_size: int
    metrics: Dict[str, float] = {}

class AggregateRequest(BaseModel):
    round_id: str
    updates: List[AggregationItem]
    strategy: str = "FedAvg"
    noise_multiplier: float = 0.0

class AggregateResponse(BaseModel):
    success: bool
    aggregated_weights: bytes
    global_metrics: Dict[str, float]

app = FastAPI(title="Secure Aggregator Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/aggregate")
async def aggregate(request: AggregateRequest) -> AggregateResponse:
    try:
        if not request.updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        model_updates = [u.weights for u in request.updates]
        sample_sizes = [max(0, int(u.sample_size)) for u in request.updates]
        if sum(sample_sizes) == 0:
            raise HTTPException(status_code=400, detail="Invalid sample sizes")

        aggregated_bytes = SecureAggregator.federated_averaging(model_updates, sample_sizes)
        if request.noise_multiplier and request.noise_multiplier > 0:
            state = torch.load(io.BytesIO(aggregated_bytes))
            noisy = SecureAggregator.add_dp_noise(state, float(request.noise_multiplier))
            out = io.BytesIO()
            torch.save(noisy, out)
            aggregated_bytes = out.getvalue()

        global_metrics: Dict[str, float] = {}
        metric_keys = set()
        for u in request.updates:
            metric_keys.update((u.metrics or {}).keys())

        total_samples = float(sum(sample_sizes))
        for key in metric_keys:
            acc = 0.0
            for u, n in zip(request.updates, sample_sizes):
                val = float((u.metrics or {}).get(key, 0.0))
                acc += val * (n / total_samples)
            global_metrics[key] = acc

        return AggregateResponse(success=True, aggregated_weights=aggregated_bytes, global_metrics=global_metrics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aggregation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
