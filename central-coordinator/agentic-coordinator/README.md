# Agentic Coordinator

LangGraph-based coordination engine for federated training rounds, cross-service workflows, and decentralized consensus.

## Port
- **`8001`** (REST API)

## Service Responsibilities
The `agentic-coordinator` is the **conductor (brain)** of the entire federated system. It runs the orchestrator that coordinates the steps between all the central services and the individual bank nodes.

1. **Managing Training Rounds (Federated Round Orchestration)**
   - **What it does:** Runs the training round from start to finish, ensuring everything happens in the right order.
   - **How it works:** It starts a round, alerts the bank nodes to train, collects their updates, handles timeouts if a bank is slow, and triggers the merging process.

2. **Handling System Failures (SAGA Orchestration Pattern)**
   - **What it does:** Ensures that if something goes wrong during a training round, the system recovers cleanly without corrupting any data.
   - **How it works:** It uses a state machine workflow (LangGraph) that detects node or communication failures and triggers compensation/rollback actions (like discarding failed updates).

3. **Voting on Fraud Patterns (Consensus & Threat Intelligence)**
   - **What it does:** Allows banks to collectively vote on new fraud patterns and share threat information.
   - **How it works:** It manages a decentralized voting protocol where a bank can propose a fraud pattern, other banks vote on its validity, and the system records the result once a consensus is reached.

4. **Service Integration**
   - **What it does:** Acts as the communication bridge between all central and local services.
   - **How it works:** It talks directly to the Secure Aggregator, Policy Manager, Model Registry, and the individual Bank Nodes to route requests, model weights, and mask keys.

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
