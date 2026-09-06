# Transaction Graph

Graph database interface, feature engineering, and CDC streaming for real-time transaction ingestion.

## Port
- **`9004`** (REST API)

## Service Responsibilities
The `transaction-graph` is the **data structure manager (graph builder)** of the bank node. It converts standard flat transaction records into interconnected network maps (graphs) and stores them.

1. **Building the Transaction Map (Graph Database Construction)**
   - **What it does:** Organizes customer accounts and payments into an interconnected graph structure.
   - **How it works:** It writes data to the local Neo4j database, representing bank accounts as "nodes" (circles) and payments/transfers as "edges" (arrows connecting the circles).

2. **Calculating Account Patterns (Dynamic Feature Engineering)**
   - **What it does:** Calculates mathematical metrics about how each account interacts in the network.
   - **How it works:** It measures details like how many accounts send money to an account (in-degree), how many receive money (out-degree), total amount sent, and transaction speeds, which are then used as input features by the GNN model.

3. **Real-Time Ingestion (Change Data Capture)**
   - **What it does:** Ingests new transaction entries instantly into the graph map as they happen.
   - **How it works:** It receives new transactions via REST APIs or Kafka event streams and updates the Neo4j database in real time.

4. **Extracting Transaction Neighborhoods (Subgraph Extraction)**
   - **What it does:** Extracts a small portion of the transaction network map around a specific account.
   - **How it works:** It queries the database to extract adjacent accounts up to a certain depth (e.g., connections within 2 hops) to help the GNN analyze localized transaction patterns.

---

## API Endpoints

### 1. General & Utility
- `GET /health`: Returns basic health status.

### 2. Graph Ingestion & Queries
- `POST /transactions`: Inserts a transaction into the Neo4j graph.
  - **Payload**: Includes `sender_id`, `receiver_id`, `amount`, `timestamp`, and `is_fraud` label (optional).
- `GET /accounts`: Lists all unique account nodes in the database.
- `GET /accounts/{account_id}/features`: Generates and returns graph features for the specified account.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEO4J_URI` | Bolt connection address for Neo4j | `"bolt://localhost:7687"` |
| `NEO4J_USER` | Neo4j username | `"neo4j"` |
| `NEO4J_PASSWORD` | Neo4j password | `"password"` |
| `KAFKA_BOOTSTRAP_SERVERS`| Kakfa message broker address | `"localhost:9092"` |

---

## Technology Stack
- **Database Engine**: Neo4j (Graph DBMS)
- **Database Drivers**: `neo4j` Python driver (Bolt protocol)
- **Framework**: FastAPI, Uvicorn, Pydantic
