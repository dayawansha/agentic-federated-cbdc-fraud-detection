# Model Registry

Model lineage tracking, evaluation metrics registry, and PyTorch model weight artifact storage.

## Port
- **`8004`** (REST API)

## Service Responsibilities
The `model-registry` service manages the ML model repository, storing training weights, validation metrics, and version identifiers for historical auditing and rollbacks.

- **Model Registration**: Processes registrations of newly trained global or local models. Generates unique version strings and stamps records with UTC timestamps.
- **Weight Serialization & Disk Storage**: Receives raw model weights (base64 encoded), decodes them, and writes them to persistent storage (`ARTIFACT_DIR`) as PyTorch `.pt` files.
- **Lineage and Metadata Tracking**: Persists evaluation metrics (accuracy, F1-score, precision, recall, AUC-ROC) along with model scopes (`is_global` flags) in PostgreSQL database tables.
- **Retrieval Interfaces**: Exposes simple endpoints to download model checkpoints, query metadata catalogs, and serve binary weights to orchestrating pipelines or agents.

---

## API Endpoints

### 1. General & Utility
- `GET /health`: Returns basic health status.

### 2. Model Registration & Query
- `POST /models/register`: Registers a model version.
  - **Payload**: Includes `version_id`, `metrics`, `artifact_path` (optional), `is_global` flag, and base64-encoded PyTorch `weights` dictionary.
- `GET /models/latest`: Returns metadata (excluding weights) for the most recently registered model version.
- `GET /models/versions`: Returns a list of all registered model versions and their performance statistics.

### 3. Artifact Delivery
- `GET /models/latest/weights`: Downloads base64-encoded weights for the latest global model.
- `GET /models/{version_id}/weights`: Downloads base64-encoded weights for a specific model version ID.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Complete PostgreSQL connection string | Constructed |
| `POSTGRES_HOST` | Database host | `"localhost"` |
| `POSTGRES_PORT` | Database port | `"5432"` |
| `POSTGRES_USER` | Database user | `"user"` |
| `POSTGRES_PASSWORD`| Database password | `"password"` |
| `POSTGRES_DB` | Database name | `"federated_fraud_db"` |
| `ARTIFACT_DIR`| Local folder path for saving binary `.pt` model weight files | `"{os.getcwd()}/artifacts"` |

---

## Technology Stack
- **Framework**: FastAPI, Uvicorn, Pydantic
- **Database Access**: SQLAlchemy Core + ORM (PostgreSQL database backend)
- **Model Checkpointing**: PyTorch-compatible serialization protocols
