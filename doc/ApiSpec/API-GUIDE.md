# API Documentation: Agentic Federated Learning Framework

This document outlines the primary REST APIs and Kafka-based integration points for the Federated CBDC Fraud Detection system.

## 1. Coordinator Domain

### Agentic Coordinator (Port 8001)
*   **POST** `/rounds/start`
    *   **Description**: Manually trigger a federated learning round. The coordinator now fetches global policies, filters agents through governance and reliability rules, validates update quality against those thresholds, screens suspicious submissions using metric sanity and peer-outlier checks, and adaptively switches between `FedAvg` and `WeightedFedAvg` when policy conditions require it.
    *   **Query Params**: `round_id` (string)
    *   **Response**: `{"status": "success", "final_state": {...}}`

### Federated Model Aggregator (Port 8002)
*   **POST** `/aggregate`
    *   **Description**: Aggregate submitted privacy-protected model updates into a new masked global model snapshot. In the current secure-aggregation path, the aggregator only decrypts masked update payloads, verifies payload commitments, and supports `FedAvg` or `WeightedFedAvg`. Aggregate unmasking is performed after aggregation using a separately escrowed aggregate mask.

### Policy Manager (Port 8003)
*   **GET** `/policies/budget/{agent_id}`
    *   **Description**: Get remaining privacy budget for a bank node.
*   **POST** `/policies/budget/update`
    *   **Body**: `{"agent_id": string, "epsilon_spent": float, "delta_spent": float}`
*   **GET** `/policies/global`
    *   **Description**: Retrieve global training governance rules, including round thresholds, encrypted-update requirements, reliability thresholds, and adaptive aggregation settings used by the coordinator.
*   **POST** `/policies/global`
    *   **Description**: Persist and version global governance rules for the current prototype.
*   **GET** `/governance/agent/{agent_id}`
    *   **Description**: Retrieve agent eligibility and minimum reliability settings used during coordinator-side selection.
*   **POST** `/governance/agent`
    *   **Description**: Create or update governance controls for a bank node.
*   **GET** `/governance/audit`
    *   **Description**: Return recent governance and privacy-budget audit events.
*   **POST** `/secure-aggregation/masks/submit`
    *   **Description**: Store an encrypted secure-aggregation mask share for a round participant.
*   **POST** `/secure-aggregation/masks/aggregate`
    *   **Description**: Combine stored mask shares into a weighted aggregate mask used to unmask only the aggregated model result.

### Model Registry (Port 8004)
*   **POST** `/models/register`
    *   **Body**: `ModelVersion` schema (version_id, metrics, artifact_path, is_global)
*   **GET** `/models/latest`
    *   **Description**: Fetch the latest global model metadata.
*   **GET** `/models/latest/weights`
    *   **Description**: Fetch the latest model artifact payload as a base64-encoded weights blob for local round bootstrap.

## 2. Bank Node Domain

### Local Agent (Port 9001)
*   **POST** `/agent/round/start`
    *   **Description**: Coordinator triggers local training round. The local agent now pulls the latest global model from the registry when available, submits protected update payloads with integrity commitments, records privacy-evaluation metrics, and can publish high-confidence illicit inference alerts into `fraud.alerts` after the round.
    *   **Query Params**: `round_id`, `agent_id`
*   **GET** `/agent/status`
    *   **Description**: Return the current local agent status and latest metrics.

### Local GNN (Port 9002)
*   **POST** `/train`
    *   **Description**: Internal trigger for the local training loop. The current prototype uses a hybrid GraphSAGE-GAT-GraphSAGE node-classification model with residual fusion, appended structural graph features, and class-balanced loss weighting. Returns weights, labeled sample size, and evaluation metrics including accuracy, precision, recall, F1-score, and ROC-AUC.
*   **GET** `/health`
    *   **Description**: Readiness check for GNN engine.

### Privacy Layer (Port 9003)
*   **POST** `/privacy/apply-dp`
    *   **Body**: `{"weights": hex_string, "noise_multiplier": float}`
    *   **Description**: Inject Gaussian noise for Differential Privacy.
*   **POST** `/privacy/prepare-secure-update`
    *   **Description**: Convert a protected model update into a masked secure-aggregation payload and return an encrypted mask share for escrow.
*   **POST** `/privacy/encrypt`
    *   **Description**: Encrypt a model artifact payload for protected transport/storage using the shared privacy transport key.
*   **POST** `/privacy/evaluate`
    *   **Description**: Produce byte-level and, when possible, tensor-level privacy-report metrics comparing raw weights, protected weights, and encrypted payload overhead.
*   **POST** `/privacy/evaluate/sweep`
    *   **Description**: Run a comparative privacy experiment across multiple noise multipliers and return a batch of privacy reports, including leakage-style proxy metrics such as cosine similarity, parameter preservation ratio, and derived leakage risk level.

### Alerting (Port 9005)
*   **Kafka Consumer**: Subscribes to `fraud.alerts` topic.
*   **GET** `/health`

## 3. Shared Schemas
Refer to `shared/schemas/models.py` for Pydantic definitions used across REST interfaces.
Refer to `shared/contracts/` for shared OpenAPI/REST contract assets.

## 4. Supporting Scripts
*   `scripts/privacy_evaluation_report.py`
    *   **Description**: Generate a single privacy evaluation report or a multi-noise comparative privacy experiment by calling the Privacy Layer `/privacy/evaluate` or `/privacy/evaluate/sweep` endpoints.
