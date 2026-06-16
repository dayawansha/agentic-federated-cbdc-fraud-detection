# Secure Aggregator

Federated model parameters aggregation (FedAvg, WeightedFedAvg), secure decryption, and global metric synthesis.

## Port
- **`8002`** (REST API)

## Service Responsibilities
The `secure-aggregator` is a high-performance computation microservice responsible for merging locally trained GNN model weights into a singular global model.

- **Federated Averaging**: Performs standard PyTorch-level `FedAvg` or custom `WeightedFedAvg` which scales client updates based on dataset sample sizes and node reliability scores.
- **Secure Payload Decryption**: Decrypts incoming encrypted weights using a symmetric transport cipher, validating SHA-256 hash commitments (both protected and encrypted) to protect against transport tampering.
- **Differential Privacy Addition**: Injectively overlays Gaussian noise onto the final aggregated global state dict according to the specified noise multiplier (ε-DP scaling).
- **Metric Consolidation**: Synthesizes local evaluation metrics (F1-score, AUC-ROC, accuracy, recall, precision) into weighted global performance metrics.

---

## API Endpoints

### 1. General & Utility
- `GET /health`: Returns basic health status.

### 2. Aggregation Logic
- `POST /aggregate`: Performs aggregation on a batch of updates.
  - **Request Body**: Takes `round_id`, a list of `updates` containing base64 serialized/encrypted weights and metadata, the chosen `strategy` (e.g. `FedAvg` or `WeightedFedAvg`), and `noise_multiplier`.
  - **Response**: Returns the base64-encoded serialized PyTorch global model weights along with the synthesized global evaluation metrics.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIVACY_FERNET_KEY` | Raw base64-encoded Fernet key (optional) | None |
| `PRIVACY_KEY_SEED`   | Seed string used to derive the AES key if no key is explicitly set | `"development-only-shared-key"` |

---

## Technology Stack
- **Core ML Framework**: PyTorch (weight loading and tensor manipulation)
- **Framework**: FastAPI, Uvicorn, Pydantic
- **Cryptography**: `cryptography` (Fernet symmetric encryption)
