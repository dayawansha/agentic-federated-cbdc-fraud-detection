import logging
import os
import uuid
import base64
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine, desc, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Model Registry Service")

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
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", os.path.abspath(os.path.join(os.getcwd(), "artifacts")))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class ModelVersionRow(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    metrics = Column(JSONB, nullable=False, default=dict)
    artifact_path = Column(String, nullable=False)
    is_global = Column(Boolean, nullable=False, default=True)

class RegisterModelRequest(BaseModel):
    version_id: Optional[str] = None
    metrics: Dict[str, float] = {}
    artifact_path: Optional[str] = None
    is_global: bool = True
    weights: Optional[str] = None

class ModelVersion(BaseModel):
    version_id: str
    created_at: datetime
    metrics: Dict[str, float]
    artifact_path: str
    is_global: bool = True

class ModelWeightsResponse(BaseModel):
    version_id: str
    weights: str

@app.on_event("startup")
async def startup_event():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/models/register")
async def register_model(request: RegisterModelRequest):
    version_id = request.version_id or f"v-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc)

    artifact_path = request.artifact_path
    if request.weights is not None:
        filename = f"{version_id}.pt"
        artifact_path = os.path.join(ARTIFACT_DIR, filename)
        with open(artifact_path, "wb") as f:
            f.write(base64.b64decode(request.weights))

    if not artifact_path:
        raise HTTPException(status_code=400, detail="artifact_path or weights must be provided")

    row = ModelVersionRow(
        version_id=version_id,
        created_at=created_at,
        metrics=request.metrics or {},
        artifact_path=artifact_path,
        is_global=bool(request.is_global),
    )
    with SessionLocal() as session:
        session.add(row)
        session.commit()

    logger.info(f"Registered new model version: {version_id}")
    return {"status": "success", "version_id": version_id}

@app.get("/models/latest")
async def get_latest_model():
    with SessionLocal() as session:
        row = session.execute(select(ModelVersionRow).order_by(desc(ModelVersionRow.created_at)).limit(1)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="No models found")
        return ModelVersion(
            version_id=row.version_id,
            created_at=row.created_at,
            metrics=row.metrics or {},
            artifact_path=row.artifact_path,
            is_global=row.is_global,
        )

def _read_artifact_base64(version_id: str, artifact_path: str) -> ModelWeightsResponse:
    if not os.path.exists(artifact_path):
        raise HTTPException(status_code=404, detail=f"Artifact not found for model version {version_id}")
    with open(artifact_path, "rb") as f:
        payload = base64.b64encode(f.read()).decode("ascii")
    return ModelWeightsResponse(version_id=version_id, weights=payload)

@app.get("/models/latest/weights", response_model=ModelWeightsResponse)
async def get_latest_model_weights():
    latest = await get_latest_model()
    return _read_artifact_base64(latest.version_id, latest.artifact_path)

@app.get("/models/{version_id}/weights", response_model=ModelWeightsResponse)
async def get_model_weights(version_id: str):
    with SessionLocal() as session:
        row = session.execute(
            select(ModelVersionRow).where(ModelVersionRow.version_id == version_id).limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Model version not found")
        return _read_artifact_base64(row.version_id, row.artifact_path)

@app.get("/models/versions", response_model=List[ModelVersion])
async def list_versions():
    with SessionLocal() as session:
        rows = session.execute(select(ModelVersionRow).order_by(desc(ModelVersionRow.created_at))).scalars().all()
        return [
            ModelVersion(
                version_id=r.version_id,
                created_at=r.created_at,
                metrics=r.metrics or {},
                artifact_path=r.artifact_path,
                is_global=r.is_global,
            )
            for r in rows
        ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
