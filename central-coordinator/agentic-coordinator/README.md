# Agentic Coordinator

LangGraph-based coordination engine for federated training rounds, cross-service workflows, and decentralized consensus.

## Port
- **`8001`** (REST API)

## Service Architecture & Responsibilities
The `agentic-coordinator` sits at the center of the federated system, orchestrating transactions and state transfers between coordinate groups and local bank nodes.

- **Federated Round Orchestration**: Manages the step-by-step lifecycle of federated training. Initiates rounds, tracks expected node responses, and enforces timeouts.
- **SAGA Orchestration Pattern**: Implements a distributed SAGA pattern using LangGraph to ensure robust rollback or compensation steps if a node fails during training, policy evaluation, or model aggregation.
- **Consensus & Threat Intelligence**: Orchestrates decentralized voting/negotiations on global variables, such as shared threat indicators or collaborative fraud pattern identification.
- **Service Integration**: Communicates directly with the `Secure Aggregator`, `Policy Manager`, and `Model Registry`, as well as `Local Agent` endpoints on individual bank nodes.

---

## API Endpoints

### 1. General & Utility
- `GET /health`: Returns basic health status.

### 2. Federated Learning Execution
- `POST /rounds/start?round_id={round_id}`: Triggers the LangGraph orchestration flow for the specified round.
- `POST /updates/submit`: Receives local model update payloads from bank nodes.
  - **Payload requirements**: Includes `agent_id`, `round_id`, encrypted weights, sample size, metrics, differential privacy verification flags, and mask shares.

### 3. Threat Consensus
- `POST /consensus/propose-fraud-pattern`: Initiates a cross-bank collaborative consensus vote for registering new fraud indicators.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_AGENT_URLS` | Comma-separated list of bank-node agents | `http://local-agent:9001` |
| `SECURE_AGGREGATOR_URL`| Destination for secure model aggregation | `http://secure-aggregator:8002` |
| `POLICY_MANAGER_URL`   | Governance, audit, and mask configuration | `http://policy-manager:8003` |
| `MODEL_REGISTRY_URL`   | ML model version metadata storage | `http://model-registry:8004` |

---

## Technology Stack
- **Core Engine**: Python 3.11+, FastAPI, Uvicorn
- **Orchestration**: LangGraph, LangChain
- **Communication**: HTTPX (Async clients), REST protocol
