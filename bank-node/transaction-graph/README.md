# Transaction Graph

Graph database interface, feature engineering, and CDC streaming for real-time transaction ingestion.

## Port
- **`9004`** (REST API)

## Service Responsibilities
The `transaction-graph` service provides the relational database layer for bank-node operations, structuring flat transaction ledgers into graph networks of accounts and payments.

- **Graph Database Construction**: Manages connections to the local Neo4j database, inserting accounts as nodes and transfers as directed `TRANSACTED` edges.
- **Dynamic Feature Engineering**: Computes local graph statistics for accounts (in-degree, out-degree, transaction counts, cumulative values, first/last transaction timestamps) to feed GNN feature matrices.
- **Real-Time Data Ingestion**: Consumes new transaction records via REST requests or Kafka events (facilitating Change Data Capture - CDC pipelines), updating the graph topology in real time.
- **Subgraph Extraction**: Offers structural subgraph queries (limiting paths by depth or node counts) to support neighborhood-based GNN inference.

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
