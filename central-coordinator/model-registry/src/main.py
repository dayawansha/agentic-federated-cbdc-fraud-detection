import logging
import os
import uuid
import base64
import boto3
from botocore.client import Config
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

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "model-artifacts")
S3_SECURE = os.getenv("S3_SECURE", "False").lower() in ("true", "1")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
        use_ssl=S3_SECURE,
    )

def _init_s3_bucket():
    if not S3_ENDPOINT_URL:
        logger.info("S3_ENDPOINT_URL not configured. Using local disk fallback for model artifacts.")
        return
    try:
        s3 = _get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET_NAME)
        logger.info(f"Connected to MinIO/S3. Bucket '{S3_BUCKET_NAME}' already exists.")
    except Exception:
        try:
            s3 = _get_s3_client()
            s3.create_bucket(Bucket=S3_BUCKET_NAME)
            logger.info(f"Connected to MinIO/S3. Created bucket '{S3_BUCKET_NAME}'.")
        except Exception as e:
            logger.error(f"Failed to initialize S3 bucket '{S3_BUCKET_NAME}': {e}")

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
    _init_s3_bucket()

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
        local_path = os.path.join(ARTIFACT_DIR, filename)
        try:
            binary_weights = base64.b64decode(request.weights)
            with open(local_path, "wb") as f:
                f.write(binary_weights)
            logger.info(f"Saved weights for {version_id} to local disk: {local_path}")
        except Exception as e:
            logger.error(f"Failed to write weights for {version_id} to local disk: {e}")

        artifact_path = local_path
        if S3_ENDPOINT_URL:
            try:
                s3 = _get_s3_client()
                binary_weights = base64.b64decode(request.weights)
                s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=f"{version_id}.pt",
                    Body=binary_weights
                )
                artifact_path = f"s3://{S3_BUCKET_NAME}/{version_id}.pt"
                logger.info(f"Uploaded weights for {version_id} to S3 bucket '{S3_BUCKET_NAME}'")
            except Exception as e:
                logger.error(f"Failed to upload weights for {version_id} to S3: {e}. Falling back to registered local path.")

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

    # MLflow tracking integration
    if MLFLOW_TRACKING_URI:
        try:
            import mlflow
            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment("federated-fraud-detection")
            with mlflow.start_run(run_name=version_id):
                for key, val in (request.metrics or {}).items():
                    try:
                        mlflow.log_metric(key, float(val))
                    except Exception:
                        pass
                mlflow.set_tag("version_id", version_id)
                mlflow.set_tag("is_global", str(request.is_global))
                mlflow.set_tag("artifact_path", artifact_path)
                
                if request.weights is not None:
                    tmp_filename = f"tmp_{version_id}.pt"
                    tmp_filepath = os.path.join(ARTIFACT_DIR, tmp_filename)
                    with open(tmp_filepath, "wb") as f:
                        f.write(base64.b64decode(request.weights))
                    mlflow.log_artifact(tmp_filepath, artifact_path="model")
                    try:
                        os.remove(tmp_filepath)
                    except Exception:
                        pass
                logger.info(f"Logged model run {version_id} to MLflow")
        except Exception as e:
            logger.error(f"Failed to log to MLflow: {e}")

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
    if artifact_path.startswith("s3://"):
        try:
            parts = artifact_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1]
            s3 = _get_s3_client()
            response = s3.get_object(Bucket=bucket, Key=key)
            payload = base64.b64encode(response["Body"].read()).decode("ascii")
            return ModelWeightsResponse(version_id=version_id, weights=payload)
        except Exception as e:
            logger.error(f"Failed to download weights for {version_id} from S3 path {artifact_path}: {e}")
            raise HTTPException(status_code=404, detail=f"S3 Artifact not found for model version {version_id}")

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
