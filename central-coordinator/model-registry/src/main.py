import logging
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Model Registry Service")

class ModelVersion(BaseModel):
    version_id: str
    created_at: datetime
    metrics: Dict[str, float]
    artifact_path: str # Path to stored model weights (e.g. S3/MinIO)
    is_global: bool = True

# In-memory storage for demonstration
model_versions: List[ModelVersion] = []

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/models/register")
async def register_model(model: ModelVersion):
    model_versions.append(model)
    logger.info(f"Registered new model version: {model.version_id}")
    return {"status": "success", "version_id": model.version_id}

@app.get("/models/latest")
async def get_latest_model():
    if not model_versions:
        raise HTTPException(status_code=404, detail="No models found")
    # Return the most recent model
    return sorted(model_versions, key=lambda x: x.created_at, reverse=True)[0]

@app.get("/models/versions", response_model=List[ModelVersion])
async def list_versions():
    return model_versions

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
