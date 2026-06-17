# Model Registry

Model lineage tracking, evaluation metrics registry, and PyTorch model weight artifact storage.

## Port
- **`8004`** (REST API)

## Service Responsibilities
The `model-registry` is the **librarian (archive cabinet)** of the AI models. It keeps track of every version of the GNN fraud-detection model, its accuracy stats, and its physical files.

1. **Registering Models (Model Registration)**
   - **What it does:** Catalogues and saves new AI models as they are created during the training rounds.
   - **How it works:** It generates a unique version name (like a stamp) and records the exact time the model was created.

2. **Saving Model Files (Weight Serialization & Disk Storage)**
   - **What it does:** Receives the AI learnings (model weights) and saves them onto the disk.
   - **How it works:** It decodes the incoming model data (sent as base64) and writes it as a PyTorch binary file (`.pt`) in a persistent folder.

3. **Tracking History & Quality (Lineage and Metadata Tracking)**
   - **What it does:** Remembers the quality metrics of every model so you can compare them or revert to a previous version if a new one performs poorly.
   - **How it works:** It writes stats like accuracy, loss, and F1-score, along with whether the model is a central global model or a bank-specific update, into the PostgreSQL database.

4. **Serving Models (Retrieval Interfaces)**
   - **What it does:** Provides the model files and performance records to other parts of the system when requested.
   - **How it works:** It exposes endpoints to download specific model weights so bank nodes can pull the latest version to start a new training round.

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
