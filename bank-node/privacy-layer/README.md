# Privacy Layer

Differential privacy injections, symmetric payload encryption, secure multi-party mask generation, and adversarial vulnerability auditing.

## Port
- **`9003`** (REST API)

## Service Responsibilities
The `privacy-layer` is a dedicated cryptography and privacy-preserving machine learning service that guarantees the confidentiality of bank-node updates before they leave the local boundary.

- **Differential Privacy (DP)**: Injects Gaussian noise directly into GNN weight tensors to comply with Epsilon-DP limits, preventing training data extraction from the aggregated parameters.
- **Symmetric Payload Protection**: Encrypts and decrypts base64 serialized PyTorch state dicts using a Fernet block cipher (AES-128 in CBC mode with HMAC authentication).
- **Secure Aggregation Masks**: Generates zero-sum additive secret mask shares. Local agents upload masked weights and distribute the shares to the coordinator, enabling secure aggregation without revealing raw model updates.
- **Vulnerability Auditing**: Runs automated security evaluation sweeps simulating adversarial attacks:
  - **Membership Inference Attacks (MIA)**: Trains shadow models to assess if an attacker can guess if a transaction was used in the training set.
  - **Link Reconstruction Attacks**: Tests if an adversary can reconstruct structural node connections from GNN weight updates.
  - Tracks attacker AUC-ROC, precision/recall, and accuracy degradation curves.

---

## API Endpoints

### 1. Cryptography & DP
- `GET /health`: Returns basic health status.
- `POST /privacy/apply-dp`: Applies Gaussian noise to model weights according to a noise multiplier.
- `POST /privacy/encrypt`: Encrypts a raw base64 string.
- `POST /privacy/decrypt`: Decrypts an encrypted payload.
- `POST /privacy/prepare-secure-update`: Prepares masked weights and split shares for the SMPC aggregation workflow.

### 2. Privacy Auditing
- `POST /privacy/evaluate`: Simulates membership inference and structural link leakage on a model.
- `POST /privacy/evaluate/sweep`: Runs an evaluation sweep across various noise scales to compute the privacy-utility curve.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIVACY_FERNET_KEY` | Raw base64-encoded Fernet key (optional) | None |
| `PRIVACY_KEY_SEED`   | Seed string used to derive the AES key if no key is explicitly set | `"development-only-shared-key"` |

---

## Technology Stack
- **Libraries**: PyTorch (weight manipulation), Cryptography (Fernet)
- **Framework**: FastAPI, Uvicorn, Pydantic
- **Adversarial Modeling**: Scikit-learn, NumPy
