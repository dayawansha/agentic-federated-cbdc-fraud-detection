# Privacy Layer

Differential privacy injections, symmetric payload encryption, secure multi-party mask generation, and adversarial vulnerability auditing.

## Port
- **`9003`** (REST API)

## Service Responsibilities
The `privacy-layer` is the **security shield** of the bank node. It ensures that the bank's AI learnings are completely safe and scrambled before they are sent over the network to the central coordinator.

1. **Adding Safety Noise (Differential Privacy)**
   - **What it does:** Prevents attackers from reverse-engineering the AI model to steal private customer transaction data.
   - **How it works:** It injects a tiny amount of mathematical random noise (Gaussian noise) into the AI model's parameters. This masks individual transaction details while keeping the overall learning patterns intact.

2. **Scrambling with Cryptographic Masks (Secure Aggregation)**
   - **What it does:** Scrambles the bank's model updates so that the coordinator cannot read them, but can still average them with other banks' updates.
   - **How it works:** It generates secret mathematical "masks" (similar to temporary keys) and adds them to the model weights. The scrambled weights are sent to the coordinator, while the secret mask key is sent to the Policy Manager. When the coordinator combines all banks' updates, the masks automatically cancel out.

3. **Locking the Data (Symmetric Encryption)**
   - **What it does:** Securely locks the model file before transmission to prevent unauthorized eyes from reading it while it travels across the network.
   - **How it works:** It encrypts the model weights using a secure AES key (Fernet block cipher). Only authorized parties with the matching key can unlock and read it.

4. **Testing for Weaknesses (Vulnerability Auditing)**
   - **What it does:** Simulates cyberattacks on the AI model to test if any private transaction data could still leak out.
   - **How it works:** It runs automated tests that mimic real-world attacks:
     - *Membership Inference Attacks:* Tests if an attacker can guess whether a specific transaction was used during training.
     - *Link Reconstruction Attacks:* Tests if an attacker can reconstruct the structural transaction network map (who sent money to whom) from the GNN updates.

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
