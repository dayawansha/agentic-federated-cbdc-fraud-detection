# API Documentation: Agentic Federated Learning Framework

This document outlines the primary API endpoints and gRPC services for the Federated CBDC Fraud Detection system.

## 1. Coordinator Domain

### Agentic Coordinator (Port 8001)
*   **POST** `/rounds/start`
    *   **Description**: Manually trigger a federated learning round.
    *   **Query Params**: `round_id` (string)
    *   **Response**: `{"status": "success", "final_state": {...}}`

### Secure Aggregator (Port 8002)
*   **gRPC Service**: `SecureAggregator`
    *   **Method**: `AggregateUpdates`
    *   **Input**: `AggregationRequest` (round_id, agent_ids, strategy)
    *   **Output**: `AggregationResponse` (success, aggregated_weights, global_metrics)

### Policy Manager (Port 8003)
*   **GET** `/policies/budget/{agent_id}`
    *   **Description**: Get remaining privacy budget for a bank node.
*   **POST** `/policies/budget/update`
    *   **Body**: `{"agent_id": string, "epsilon_spent": float, "delta_spent": float}`
*   **GET** `/policies/global`
    *   **Description**: Retrieve global training governance rules.

### Model Registry (Port 8004)
*   **POST** `/models/register`
    *   **Body**: `ModelVersion` schema (version_id, metrics, artifact_path, is_global)
*   **GET** `/models/latest`
    *   **Description**: Fetch the latest global model metadata.

## 2. Bank Node Domain

### Local Agent (Port 9001)
*   **POST** `/agent/round/start`
    *   **Description**: Coordinator triggers local training round.
    *   **Query Params**: `round_id`, `agent_id`
*   **gRPC Service**: `FederatedAgent`
    *   **Method**: `StartTrainingRound`

### Local GNN Model (Port 9002)
*   **POST** `/train`
    *   **Description**: Internal trigger for local training loop.
*   **GET** `/health`
    *   **Description**: Readiness check for GNN engine.

### Privacy Layer (Port 9003)
*   **POST** `/privacy/apply-dp`
    *   **Body**: `{"weights": hex_string, "noise_multiplier": float}`
    *   **Description**: Inject Gaussian noise for Differential Privacy.
*   **POST** `/privacy/encrypt`
    *   **Description**: AES-256 encryption of model artifacts.

### Alerting (Port 9005)
*   **Kafka Consumer**: Subscribes to `fraud.alerts` topic.
*   **GET** `/health`

## 3. Shared Schemas
Refer to `shared/schemas/models.py` for Pydantic definitions used across REST interfaces.
Refer to `shared/proto/federated.proto` for gRPC service definitions.
