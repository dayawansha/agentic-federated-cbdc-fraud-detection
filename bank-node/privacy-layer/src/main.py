import io
import logging

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.privacy_engine import privacy_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Privacy Layer Service")

class DPRequest(BaseModel):
    weights: bytes
    noise_multiplier: float = 0.01

class DPResponse(BaseModel):
    weights: bytes

class EncryptRequest(BaseModel):
    data: bytes

class EncryptResponse(BaseModel):
    encrypted_data: bytes

class DecryptRequest(BaseModel):
    encrypted_data: bytes

class DecryptResponse(BaseModel):
    data: bytes

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/privacy/apply-dp")
async def apply_dp(request: DPRequest) -> DPResponse:
    try:
        # Load weights from bytes
        buffer = io.BytesIO(request.weights)
        weights_dict = torch.load(buffer)
        
        # Apply DP
        private_weights = privacy_module.process_weights_for_federation(weights_dict, request.noise_multiplier)
        
        # Serialize back to bytes
        output_buffer = io.BytesIO()
        torch.save(private_weights, output_buffer)
        
        return DPResponse(weights=output_buffer.getvalue())
    except Exception as e:
        logger.error(f"Error applying DP: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/encrypt")
async def encrypt(request: EncryptRequest) -> EncryptResponse:
    try:
        return EncryptResponse(encrypted_data=privacy_module.encrypt_model(request.data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/privacy/decrypt")
async def decrypt(request: DecryptRequest) -> DecryptResponse:
    try:
        return DecryptResponse(data=privacy_module.decrypt_model(request.encrypted_data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9003)
