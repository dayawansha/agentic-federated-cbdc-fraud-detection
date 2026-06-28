# Federated Model Aggregator

Federated model parameters aggregation (`FedAvg`, `WeightedFedAvg`, `PerformanceWeightedFedAvg`, `AdaptiveFedAvg`, `FedProxGNN`, `FedGraph`, `RobustMedian`), secure decryption, and global metric synthesis.

## Port
- **`8002`** (REST API)

## Service Responsibilities
The `federated-model-aggregator` is the **merging engine (math brain)** of the system. It combines all the separate models trained by individual banks into a single, improved global model.

1. **Merging Model Weights (Federated Averaging)**
   - **What it does:** Combines individual AI models from various banks into one master model.
   - **How it works:** It supports multiple strategies:
     - `FedAvg`: sample-size weighted averaging.
     - `WeightedFedAvg`: sample size plus agent reliability weighting.
     - `PerformanceWeightedFedAvg`: weights strong local models more heavily using their reported metrics.
     - `AdaptiveFedAvg`: blends sample size, reliability, and model quality.
     - `FedProxGNN`: coordinator-side proximal weighting that down-weights updates that drift too far from the current global reference model.
     - `FedGraph`: graph-aware weighting that rewards updates trained on stronger local graph coverage and graph quality signals.
     - `RobustMedian`: coordinate-wise median aggregation that is more resilient to outlier updates.

2. **Secure Decryption & Tamper Checking**
   - **What it does:** Unlocks the incoming model weights securely and checks that they were not altered during transmission.
   - **How it works:** It decrypts the incoming model payload using secure keys and verifies SHA-256 checksums to make sure the data wasn't tampered with while traveling over the network.

3. **Adding Global Privacy Noise (Differential Privacy)**
   - **What it does:** Injects a final layer of safety noise to the merged model so no one can extract details about individual banks' datasets from it.
   - **How it works:** It adds random Gaussian noise to the aggregated global model parameters according to the system's global privacy limits.

4. **Consolidating Performance Metrics**
   - **What it does:** Summarizes how well the model is performing at detecting fraud across all banks.
   - **How it works:** It takes individual banks' performance stats (accuracy, F1-score, precision, recall) and calculates a weighted average to produce a single set of global performance metrics.

---

## API Endpoints

### 1. General & Utility
- `GET /health`: Returns basic health status.

### 2. Aggregation Logic
- `POST /aggregate`: Performs aggregation on a batch of updates.
  - **Request Body**: Takes `round_id`, a list of `updates` containing base64 serialized/encrypted weights and metadata, the chosen `strategy`, optional `global_reference_weights` for `FedProxGNN`, and `noise_multiplier`.
  - **Response**: Returns the base64-encoded serialized PyTorch global model weights along with the synthesized global evaluation metrics.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIVACY_FERNET_KEY` | Raw base64-encoded Fernet key (optional) | None |
| `PRIVACY_KEY_SEED`   | Seed string used to derive the AES key if no key is explicitly set | `"development-only-shared-key"` |
| `FEDPROX_MU` | Strength of the coordinator-side proximal penalty used by `FedProxGNN` | `1.0` |

---

## Technology Stack
- **Core ML Framework**: PyTorch (weight loading and tensor manipulation)
- **Framework**: FastAPI, Uvicorn, Pydantic
- **Cryptography**: `cryptography` (Fernet symmetric encryption)
