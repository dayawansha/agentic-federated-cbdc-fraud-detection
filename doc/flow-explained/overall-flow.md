# Federated CBDC Fraud Detection: Sequence Flow Explained

This document provides a detailed step-by-step walkthrough of the entire system lifecycle as represented in the sequence diagram [overall-sequence-v4.0.md](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/doc/design/overall-sequence-v4.0.md). 

The flow is divided into 6 logical phases, orchestrating real-time transaction ingestion, rule evaluation, live dashboard tracking, federated learning round control, local graph machine learning on bank nodes, secure privacy-preserving weight aggregation, and post-round model inference.

---

## 🏛️ System Participants & Services

Before diving into the steps, here is an overview of the key components involved:
- **CBDC Core / Payment Rail**: The central ledger or external network generating CBDC payment transactions.
- **[transaction-graph](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/transaction-graph) (Port 9004)**: Manages local graph datasets, connects to Neo4j, and exports node/edge features.
- **Neo4j DB (Port 7474/7687)**: Graph Database storage containing CBDC accounts, transaction history, and relationships.
- **Kafka Bus (Port 9092)**: Streaming broker handling event pipelines for Change Data Capture (CDC) and alerts.
- **[alerting](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/alerting) (Port 9005)**: Evaluates rule-based metrics, publishes to Kafka, saves alert records in PostgreSQL, and dispatches UI messages.
- **[fraud-dashboard](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/fraud-dashboard) (Port 3000)**: Operator interface displaying live status charts, system resources, and fraud alert feeds.
- **[local-agent](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/local-agent) (Port 9001)**: The brain of the local bank node. Runs Q-learning adaptive tuning, resource profiling, and coordinates graph processing.
- **[local-gnn](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/local-gnn-model) (Port 9002)**: Runs PyTorch Geometric training, semi-supervised graph algorithms, and inference.
- **[privacy-layer](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/privacy-layer) (Port 9003)**: Copes with sensitivity limits via gradient clipping, applies Differential Privacy noise, and handles Secure Aggregation (SecAgg).
- **[agentic-coordinator](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/central-coordinator/agentic-coordinator) (Port 8001)**: Coordinates global federated learning rounds, peer negotiation, and model validation.
- **[federated-model-aggregator](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/central-coordinator/federated-model-aggregator) (Port 8002)**: Combines models using strategies like FedAvg and RobustMedian.
- **[policy-manager](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/central-coordinator/policy-manager) (Port 8003)**: Governs privacy budget allocations (epsilon/delta limits) and holds Secure Aggregation escrow keys.
- **[model-registry](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/central-coordinator/model-registry) (Port 8004)**: Manages global model checkpoints, versions, metadata, and MLflow logging.

---

## 🔁 Step-by-Step Flow Explanation

### Phase 1: Real-time Ingestion, Rule-Based Alerting, and Change Data Capture (CDC)

This phase covers how transaction events enter the bank node, get written to the database, and trigger immediate rule-based fraud warnings.

*   **Step 1 (`CBDC -> TG`)**: The CBDC Payment Rail posts a new transaction to the `/transactions` endpoint of the `transaction-graph` service. The payload includes parameters such as `transaction_id`, `source` account, `target` account, transaction `amount`, and `asset_type`.
*   **Step 2 (`TG -> N4J`)**: The `transaction-graph` service processes this payload and writes the transaction node, source/target account nodes, and relationship links directly to the **Neo4j Database** for graph storage.
*   **Step 3 (`TG -> CBDC`)**: Once database write confirms, the `transaction-graph` service replies with `200 OK (success=True)` to release the payment rail.
*   **Step 4 (`TG -> KF`)**: The `transaction-graph` service publishes a Change Data Capture (CDC) event representing the new transaction onto the Kafka topic `transactions.events`.
*   **Step 5 (`AL -> KF`)**: The `alerting` service consumes the raw transaction event from the `transactions.events` Kafka topic.
*   **Step 6 (`AL -> AL`)**: The `alerting` service evaluates rule-based heuristic logic in real time. Rules checked include transactions exceeding a specific limit (e.g. `$10K` or `$50K`), self-transfers, and high-frequency velocity checks.
*   **Step 7 (`AL -> KF`)**: If any of the rules are violated, an alert with a high risk score ($\ge 0.5$) is generated and published to the `fraud.alerts` Kafka topic.
*   **Step 8 (`AL -> AL`, `AL -> FD`)**: The `alerting` service consumes from the `fraud.alerts` topic (which aggregates alerts from both rule-based checks and GNN predictions). The service:
    1.  Persists the alarm ticket as an `AlertRecord` in PostgreSQL.
    2.  Dispatches outbound notifications (via Slack Webhooks, Email, or SMS).
    3.  Broadcasts the alert JSON payload to the operator's browser UI (`fraud-dashboard`) via a WebSocket connection (`/ws/alerts`).

---

### Phase 2: Live UI Dashboard Monitoring & Status Polling

This phase describes how the React UI dashboard queries system metrics and displays alerts.

*   **Step 9 & 10 (`FD -> LA -> FD`)**: Every 5 seconds, the `fraud-dashboard` polls the `local-agent` (`GET /agent/status`). The agent returns accuracy metrics from the prior round, local training status, and macOS host hardware constraints (CPU load and Battery percentage).
*   **Step 11 & 12 (`FD -> AL -> FD`)**: The dashboard polls the `alerting` service (`GET /alerts/recent?limit=50`) to retrieve a list of the 50 most recent fraud tickets for the active feed.
*   **Step 13 & 14 (`FD -> AL -> FD`)**: The dashboard requests an alert overview (`GET /alerts/summary`) to render severity counts, aggregate threat levels, and open issue charts on the screen.

---

### Phase 3: Federated Learning Round Initialization & Governance Check

This phase orchestrates how the central coordinator kicks off a federated learning training round and validates participating bank node compliance.

*   **Step 15 & 16 (`AC -> PM -> AC`)**: The central `agentic-coordinator` fetches global parameters from the `policy-manager` (`GET /policies/global`). The policy manager returns rules such as the minimum number of agents required to join, allowed asset lists, and reliability score thresholds.
*   **Step 17 & 18 (`AC -> MR -> AC`)**: The coordinator calls the `model-registry` (`GET /models/latest`) to identify the baseline model version and retrieve its storage location (`artifact_path`).
*   **Step 19 & 20 (`AC -> LA -> AC`)**: The coordinator iterates through registered bank node URLs and fires a health check request (`GET /health`) to verify if the bank is online.
*   **Step 21 & 22 (`AC -> PM -> AC`)**: The coordinator checks the agent's governance profile (`GET /governance/agent/{agent_id}`) at the `policy-manager` to ensure the agent is active, has a sufficient reliability index, and is eligible to handle the asset types of this round.
*   **Step 23 & 24 (`AC -> PM -> AC`)**: The coordinator checks the agent's remaining privacy budget (`GET /policies/budget/{agent_id}`) at the `policy-manager` to verify that the node has enough privacy reserve (`epsilon` and `delta` balances) remaining to run training.
*   **Step 25 (`AC -> AC`)**: The coordinator compiles a sanitized participant registry containing only healthy, compliant, and privacy-budget-valid bank nodes.

---

### Phase 4: Local GNN Training & Adaptive Execution (Bank Node Pipeline)

This phase represents the core of the local learning process on each bank node, showing resource-aware parameter optimization, GNN execution, Differential Privacy injection, and cryptographic Secure Aggregation masking.

*   **Step 26 (`AC -> LA`)**: The coordinator triggers the round training pipeline on the selected bank node (`POST /agent/round/start`), passing the `round_id`, optimization `strategy` (e.g. FedAvg, FedProx), and global parameters.
*   **Step 27 (`LA -> LA`)**: The `local-agent` queries its local macOS host system metrics using python libraries: `psutil` checks CPU/Memory utilization, and `pmset` reads battery remaining and power source status.
*   **Step 28 & 29 (`LA -> PM -> LA`)**: The agent calls the `policy-manager` to verify that its current local privacy budget allocation allows additional noise scaling.
*   **Step 30 - 34 (`LA -> LA`)**: The local agent runs a **Q-Learning Reinforcement Learning loop** to optimize GNN hyperparameters:
    *   *State Space*: Discretized resource pressures (e.g. high CPU load, battery operating under 30%), sparse label pressure, and remaining privacy budget pressure.
    *   *Q-table updates*: The agent utilizes performance rewards (accuracy gain vs. resource costs) from past rounds to update its Q-value mapping.
    *   *Action Selection*: The agent chooses actions that adjust local execution settings, such as reducing GNN epochs if battery is low, increasing differential privacy noise if budget is tight, tuning the FedProx proximal coefficient ($\mu$), or scaling pseudo-label weights.
*   **Step 35 & 36 (`LA -> MR -> LA`)**: The agent calls `model-registry` (`GET /models/{version_id}/weights`) to download the current global GNN model base weights (returned as a base64 string).
*   **Step 37 (`LA -> TG`)**: The agent calls the `transaction-graph` service (`GET /graph/export-tensors`) to request graph training datasets.
*   **Step 38 - 40 (`TG -> N4J -> TG -> LA`)**: The `transaction-graph` service queries Neo4j to extract graph structures. The queries retrieve nodes with advanced topological features: node degree, average neighborhood degree, in-degree/out-degree ratios, and relationship directions. Neo4j returns the data, and the service formats it into PyTorch-compatible node tensors and edge index lists.
*   **Step 41 (`LA -> LG`)**: The agent sends these formatted tensors, GNN base weights, and hyperparameters to the `local-gnn` service (`POST /train`).
*   **Step 42 (`LG -> LG`)**: *Optional*: If label propagation is enabled to handle sparse datasets, `local-gnn` runs a label propagation pass to infer structural pseudo-labels for unlabeled transactions (class 2) based on neighboring connections.
*   **Step 43 (`LG -> LG`)**: The GNN service runs GNN training (using GCN or GraphSAGE architectures in PyTorch Geometric) to compute GNN weights, logging accuracy and loss metrics.
*   **Step 44 & 45 (`LG -> LA`)**: The GNN service returns the trained local weights and metric dictionary to the `local-agent`.
*   **Step 46 & 47 (`LA -> PL -> LA`)**: The agent passes the raw GNN weight update to the local `privacy-layer` (`POST /privacy/clip-gradients`). The privacy layer clips the gradients to a maximum threshold to limit sensitivity.
*   **Step 48 & 49 (`LA -> PL -> LA`)**: The agent requests DP application (`POST /privacy/apply-dp`). The `privacy-layer` injects calibrated Gaussian noise based on the Q-learning selected noise scale to secure the weights against reverse-engineering attacks.
*   **Step 50 - 54 (`LA -> PL -> PM -> PL -> LA`)**: To prevent the central coordinator from inspecting raw individual models during aggregation, the agent calls the `privacy-layer` to apply Secure Aggregation (SecAgg):
    1.  The `privacy-layer` requests the central escrow X25519 public key from the `policy-manager`.
    2.  The `privacy-layer` generates zero-sum pairwise masking shares.
    3.  It masks the GNN weights with these zero-sum matrices and encrypts the mask reconstruction share using the escrow public key.
    4.  It returns the `masked_weights` and `encrypted_mask_share` to the `local-agent`.
*   **Step 55 & 56 (`LA -> PL -> LA`)**: The agent encrypts the update payload using symmetric transport encryption via the `privacy-layer`.
*   **Step 57 (`LA -> AC`)**: The bank node submits its encrypted updates, local performance metrics, and the encrypted mask share back to the `agentic-coordinator` (`POST /updates/submit`).
*   **Step 58 & 59 (`AC -> PM -> AC`)**: The coordinator escrows the encrypted mask share by posting it to the `policy-manager` for safekeeping.

---

### Phase 5: Weight Consensus, Decryption, and Global Aggregation

This phase describes how the central coordinator verifies weight contributions, decrypts model changes without exposing individual data, rejects malicious updates, and publishes a new global GNN model.

*   **Step 60 (`AC -> AC`)**: The coordinator waits for all compliant bank nodes to submit their updates or hits the round timeout threshold.
*   **Step 61 - 63 (`AC -> LA -> AC`)**: *Weight Consensus Negotiation*: The coordinator facilitates peer weight negotiation. It prompts active agents (`POST /agent/negotiate/propose-weights`) to vote on peer contribution weights based on dataset size and node reliability. The coordinator tabulates these votes to compile consensus weight ratios.
*   **Step 64 - 66 (`AC -> PM -> AC`)**: *Mask Decryption & Cancellation*:
    1.  The coordinator requests mask reconstruction from the `policy-manager` (`POST /secure-aggregation/masks/aggregate`).
    2.  The `policy-manager` uses its escrow private key to decrypt all collected mask shares and sums them.
    3.  Because the masks are mathematically designed to sum to zero across all participants, the aggregate mask reconstructs the exact combined offset.
    4.  The manager returns this combined offset mask to the coordinator. The coordinator subtracts it from the summed weights, leaving the exact aggregate model weight sum without exposing any individual node's model.
*   **Step 67 - 73 (`AC -> SA -> AC -> MR -> AC`)**: *Model Rejection & Re-aggregation Loop*:
    1.  The coordinator posts the combined weights to the `federated-model-aggregator` (`POST /aggregate`), specifying the aggregation strategy (e.g. FedAvg, RobustMedian).
    2.  The aggregator returns the combined weights and validation score.
    3.  The coordinator fetches the previous baseline model metrics from the `model-registry` (`GET /models/latest`).
    4.  It compares validation performance. If a accuracy degradation exceedance occurs (e.g. drop $> 0.08$) or score falls below policy threshold, the coordinator isolates the worst performing bank node update, updates its profile, switches to a robust strategy (like `RobustMedian`), and restarts the aggregation loop.
    5.  Once the model passes validation limits, it exits the retry loop.
*   **Step 74 - 76 (`AC -> MR -> AC`)**: The coordinator posts the finalized GNN weights to the `model-registry` (`POST /models/register`). The registry saves the model version checkpoint, uploads the binary file to object storage (MinIO/S3), logs the parameters to MLflow, and returns the new `version_id`.
*   **Step 77 - 79 (`AC -> PM -> AC`)**: The coordinator updates privacy budgets at the `policy-manager` (`POST /policies/budget/update`), deducting the `epsilon` and `delta` spend for this round. The coordinator marks the round complete.

---

### Phase 6: Post-Round Local GNN Inference & Alert Dispatch

This phase details how local nodes use the updated global model to run fraud inference on their local transaction networks.

*   **Step 80 & 81 (`LA -> MR -> LA`)**: The `local-agent` pulls the newly aggregated global GNN model weights from the `model-registry` (`GET /models/latest/weights`).
*   **Step 82 & 83 (`LA -> LG -> LA`)**: The agent sends these weights to `local-gnn` (`POST /infer`) to run local inference. The model evaluates the local transaction graph (augmented with Neo4j-derived topological structural features) and predicts fraud risk. The GNN service returns predictions containing risk probabilities.
*   **Step 84 & 85 (`LA -> KF`)**: The local agent filters transactions predicted as high risk and publishes alert payloads directly to the `fraud.alerts` Kafka topic. This routes them into Phase 1's alerting and dashboard notification loop.
