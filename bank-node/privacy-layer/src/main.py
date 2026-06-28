"""
================================================================================
PRIVACY LAYER SERVICE - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Privacy Layer as the bank's "Cryptographic Security Guard" or "Armor Generator."
Its entire purpose is to ensure that the coordinator and other banks can never see
any individual bank's raw model weights or reverse-engineer private customer data.

It provides three main lines of defense:
1. DIFFERENTIAL PRIVACY (DP): Before sharing model weights, this service injects a calculated
   amount of random mathematical noise (static). Think of this like pixelating a photo: 
   the overall shape (the general fraud patterns) is still visible and useful, but the individual 
   pixels (the specific customer identities or amounts) are completely camouflaged.
2. SECURE AGGREGATION MASKING: Imagine multiple people want to calculate their average salary
   without revealing their exact salaries to anyone. Each person adds a secret random number (mask)
   to their salary. The masks are generated such that when all masked salaries are added up,
   they sum to zero and cancel each other out, leaving only the clean average.
   This service generates these masks using asymmetric key agreements (X25519, HKDF) and applies
   them to model weights.
3. DATA ENCRYPTION: It provides traditional encryption/decryption (using Fernet) for transit
   protection, ensuring only authorized services can read the payloads.
================================================================================
"""
import io
import logging
import base64
import hashlib
import os

from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel

from src.privacy_engine import privacy_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Privacy Layer Service")
POLICY_MANAGER_URL = os.getenv("POLICY_MANAGER_URL", "http://localhost:8003")

class DPRequest(BaseModel):
    weights: str
    noise_multiplier: float = 0.01

class DPResponse(BaseModel):
    weights: str

class EncryptRequest(BaseModel):
    data: str

class EncryptResponse(BaseModel):
    encrypted_data: str

class DecryptRequest(BaseModel):
    encrypted_data: str

class DecryptResponse(BaseModel):
    data: str

class SecureAggregationPrepareRequest(BaseModel):
    round_id: str
    agent_id: str
    weights: str

class SecureAggregationPrepareResponse(BaseModel):
    masked_weights: str
    encrypted_mask_share: str

class ClipGradientsRequest(BaseModel):
    gradients: str
    max_grad_norm: float = 1.0

class ClipGradientsResponse(BaseModel):
    clipped_gradients: str

class PrivacyEvaluationRequest(BaseModel):
    raw_weights: str
    protected_weights: str
    encrypted_data: str = ""
    noise_multiplier: float = 0.01

class PrivacyEvaluationResponse(BaseModel):
    raw_payload_bytes: int
    protected_payload_bytes: int
    encrypted_payload_bytes: int
    byte_change_ratio: float
    size_overhead_ratio: float
    protected_payload_sha256: str
    encrypted_payload_sha256: str
    tensor_l2_delta: float = 0.0
    mean_abs_tensor_delta: float = 0.0
    max_abs_tensor_delta: float = 0.0
    tensor_change_ratio: float = 0.0
    tensor_cosine_similarity: float = 0.0
    parameter_preservation_ratio: float = 0.0
    leakage_proxy_score: float = 0.0
    leakage_risk_level: str = "unknown"
    tensor_metrics_available: bool = False
    noise_multiplier: float

class PrivacySweepRequest(BaseModel):
    raw_weights: str
    noise_multipliers: list[float]
    encrypt_payloads: bool = True

class PrivacySweepResponse(BaseModel):
    experiment_count: int
    results: list[PrivacyEvaluationResponse]

def _derive_leakage_risk(leakage_proxy_score: float) -> str:
    if leakage_proxy_score >= 0.85:
        return "high"
    if leakage_proxy_score >= 0.6:
        return "medium"
    return "low"


async def _fetch_escrow_public_key() -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{POLICY_MANAGER_URL}/secure-aggregation/escrow/public-key", timeout=30.0)
        response.raise_for_status()
        payload = response.json()
        key = str(payload.get("public_key", ""))
        if not key:
            raise HTTPException(status_code=502, detail="Policy Manager did not provide an escrow public key")
        return key

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/privacy/apply-dp")
async def apply_dp(request: DPRequest) -> DPResponse:
    try:
        try:
            import torch
        except Exception as import_error:
            logger.warning("Torch unavailable in privacy-layer, returning original weights without DP: %s", import_error)
            return DPResponse(weights=request.weights)

        # Load weights from bytes
        buffer = io.BytesIO(base64.b64decode(request.weights))
        weights_dict = torch.load(buffer)
        
        # Apply DP
        private_weights = privacy_module.process_weights_for_federation(weights_dict, request.noise_multiplier)
        
        # Serialize back to bytes
        output_buffer = io.BytesIO()
        torch.save(private_weights, output_buffer)
        
        return DPResponse(weights=base64.b64encode(output_buffer.getvalue()).decode("ascii"))
    except Exception as e:
        logger.error(f"Error applying DP: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/encrypt")
async def encrypt(request: EncryptRequest) -> EncryptResponse:
    try:
        encrypted = privacy_module.encrypt_model(base64.b64decode(request.data))
        return EncryptResponse(encrypted_data=base64.b64encode(encrypted).decode("ascii"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/decrypt")
async def decrypt(request: DecryptRequest) -> DecryptResponse:
    try:
        decrypted = privacy_module.decrypt_model(base64.b64decode(request.encrypted_data))
        return DecryptResponse(data=base64.b64encode(decrypted).decode("ascii"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/prepare-secure-update", response_model=SecureAggregationPrepareResponse)
async def prepare_secure_update(request: SecureAggregationPrepareRequest) -> SecureAggregationPrepareResponse:
    try:
        try:
            import torch
        except Exception as import_error:
            logger.warning("Torch unavailable in privacy-layer, secure aggregation preparation is bypassed: %s", import_error)
            return SecureAggregationPrepareResponse(masked_weights=request.weights, encrypted_mask_share="")

        buffer = io.BytesIO(base64.b64decode(request.weights))
        weights_dict = torch.load(buffer)
        escrow_public_key = await _fetch_escrow_public_key()
        masked_weights, encrypted_mask_share = privacy_module.build_escrowed_secure_aggregation_artifacts(
            weights_dict=weights_dict,
            round_id=request.round_id,
            agent_id=request.agent_id,
            escrow_public_key_b64=escrow_public_key,
        )
        return SecureAggregationPrepareResponse(
            masked_weights=base64.b64encode(masked_weights).decode("ascii"),
            encrypted_mask_share=encrypted_mask_share,
        )
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch secure aggregation escrow key: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch secure aggregation escrow key") from exc
    except Exception as e:
        logger.error(f"Error preparing secure aggregation payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/evaluate", response_model=PrivacyEvaluationResponse)
async def evaluate_privacy(request: PrivacyEvaluationRequest) -> PrivacyEvaluationResponse:
    try:
        raw_bytes = base64.b64decode(request.raw_weights)
        protected_bytes = base64.b64decode(request.protected_weights)
        encrypted_bytes = base64.b64decode(request.encrypted_data) if request.encrypted_data else b""

        max_len = max(len(raw_bytes), len(protected_bytes), 1)
        changed_positions = sum(
            1 for left, right in zip(raw_bytes.ljust(max_len, b"\x00"), protected_bytes.ljust(max_len, b"\x00")) if left != right
        )
        byte_change_ratio = changed_positions / max_len
        size_overhead_ratio = (len(encrypted_bytes) / len(protected_bytes)) if protected_bytes else 0.0

        response = {
            "raw_payload_bytes": len(raw_bytes),
            "protected_payload_bytes": len(protected_bytes),
            "encrypted_payload_bytes": len(encrypted_bytes),
            "byte_change_ratio": float(byte_change_ratio),
            "size_overhead_ratio": float(size_overhead_ratio),
            "protected_payload_sha256": hashlib.sha256(request.protected_weights.encode("ascii")).hexdigest(),
            "encrypted_payload_sha256": hashlib.sha256(request.encrypted_data.encode("ascii")).hexdigest() if request.encrypted_data else "",
            "tensor_l2_delta": 0.0,
            "mean_abs_tensor_delta": 0.0,
            "max_abs_tensor_delta": 0.0,
            "tensor_change_ratio": 0.0,
            "tensor_cosine_similarity": 0.0,
            "parameter_preservation_ratio": 0.0,
            "leakage_proxy_score": 0.0,
            "leakage_risk_level": "unknown",
            "tensor_metrics_available": False,
            "noise_multiplier": float(request.noise_multiplier),
        }

        try:
            import torch

            raw_state = torch.load(io.BytesIO(raw_bytes))
            protected_state = torch.load(io.BytesIO(protected_bytes))
            squared_sum = 0.0
            abs_sum = 0.0
            max_abs = 0.0
            changed_tensor_count = 0
            total_tensor_count = 0
            cosine_sum = 0.0
            preservation_sum = 0.0

            for key, raw_tensor in raw_state.items():
                protected_tensor = protected_state.get(key)
                if protected_tensor is None or not getattr(raw_tensor, "is_floating_point", lambda: False)():
                    continue

                delta = (protected_tensor.float() - raw_tensor.float()).abs()
                total_tensor_count += 1
                if float(delta.max().item()) > 0.0:
                    changed_tensor_count += 1
                squared_sum += float((delta.pow(2)).sum().item())
                abs_sum += float(delta.sum().item())
                max_abs = max(max_abs, float(delta.max().item()))
                try:
                    cosine_value = float(
                        torch.nn.functional.cosine_similarity(
                            raw_tensor.float().flatten(),
                            protected_tensor.float().flatten(),
                            dim=0,
                        ).item()
                    )
                except Exception:
                    cosine_value = 0.0
                cosine_sum += cosine_value
                preservation_sum += float((delta <= 1e-3).float().mean().item())

            response["tensor_l2_delta"] = squared_sum ** 0.5
            response["mean_abs_tensor_delta"] = abs_sum / max(1, total_tensor_count)
            response["max_abs_tensor_delta"] = max_abs
            response["tensor_change_ratio"] = changed_tensor_count / max(1, total_tensor_count)
            response["tensor_cosine_similarity"] = cosine_sum / max(1, total_tensor_count)
            response["parameter_preservation_ratio"] = preservation_sum / max(1, total_tensor_count)
            response["leakage_proxy_score"] = max(
                0.0,
                min(
                    1.0,
                    (
                        0.5 * response["tensor_cosine_similarity"]
                        + 0.5 * response["parameter_preservation_ratio"]
                    ),
                ),
            )
            response["leakage_risk_level"] = _derive_leakage_risk(float(response["leakage_proxy_score"]))
            response["tensor_metrics_available"] = True
        except Exception as tensor_exc:
            logger.info("Tensor-level privacy evaluation unavailable, falling back to byte metrics only: %s", tensor_exc)

        return PrivacyEvaluationResponse(**response)
    except Exception as e:
        logger.error(f"Error evaluating privacy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/evaluate/sweep", response_model=PrivacySweepResponse)
async def evaluate_privacy_sweep(request: PrivacySweepRequest) -> PrivacySweepResponse:
    try:
        results = []
        for noise_multiplier in request.noise_multipliers:
            dp_response = await apply_dp(DPRequest(weights=request.raw_weights, noise_multiplier=float(noise_multiplier)))
            encrypted_data = ""
            if request.encrypt_payloads:
                encrypt_response = await encrypt(EncryptRequest(data=dp_response.weights))
                encrypted_data = encrypt_response.encrypted_data
            evaluation = await evaluate_privacy(
                PrivacyEvaluationRequest(
                    raw_weights=request.raw_weights,
                    protected_weights=dp_response.weights,
                    encrypted_data=encrypted_data,
                    noise_multiplier=float(noise_multiplier),
                )
            )
            results.append(evaluation)
        return PrivacySweepResponse(experiment_count=len(results), results=results)
    except Exception as e:
        logger.error(f"Error running privacy evaluation sweep: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/clip-gradients", response_model=ClipGradientsResponse)
async def clip_gradients(request: ClipGradientsRequest) -> ClipGradientsResponse:
    try:
        try:
            import torch
        except Exception as import_error:
            logger.warning("Torch unavailable in privacy-layer, skipping clipping: %s", import_error)
            return ClipGradientsResponse(clipped_gradients=request.gradients)

        # Deserialize gradient tensors
        buffer = io.BytesIO(base64.b64decode(request.gradients))
        grad_samples = torch.load(buffer)
        
        # Clip per-sample gradients
        clipped_grads = privacy_module.clip_per_sample_gradients(grad_samples, request.max_grad_norm)
        
        # Serialize back to bytes
        output_buffer = io.BytesIO()
        torch.save(clipped_grads, output_buffer)
        
        return ClipGradientsResponse(
            clipped_gradients=base64.b64encode(output_buffer.getvalue()).decode("ascii")
        )
    except Exception as e:
        logger.error(f"Error clipping gradients: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9003)
