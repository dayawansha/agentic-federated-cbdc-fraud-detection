# Policy Manager

Governance, compliance auditing, privacy budget enforcement (ε, δ), and secure aggregation mask tracking.

## Port
- **`8003`** (REST API)

## Service Responsibilities
The `policy-manager` acts as the system's compliance and security guard, regulating interactions based on strict privacy bounds and logging administrative decisions.

- **Privacy Budget Management**: Enforces Differential Privacy limits per bank node. Deducts used budget (ε, δ) following training rounds, and rejects participation if a node's cumulative budget exceeds maximum thresholds.
- **System Governance**: Stores global coordination configuration parameters including minimum participation ratio, default noise multiplier, and model validation thresholds.
- **Node Lifecycle & Reliability**: Manages node status registrations (active/inactive) and updates reliability scores dynamically based on communication latency and participation completion metrics.
- **Audit Logging**: Logs immutable security events (registrations, budget updates, policy changes, aggregation rounds) to database tables for compliance tracking.
- **Secure Aggregation Coordination**: Manages the multi-party computation (MPC) mask database. Collects mask shares from participating nodes and computes the cumulative zero-sum masks required by the aggregator.

---

## API Endpoints

### 1. Privacy Budgets
- `GET /policies/budget/{agent_id}`: Fetches the current and maximum privacy budget (Epsilon, Delta) for an agent.
- `POST /policies/budget/update`: Subtracts Epsilon/Delta usage for an agent after a round.
- `POST /policies/budget/set`: Initializes or forces a custom budget config for an agent.

### 2. Global Policies
- `GET /policies/global`: Fetches current system-wide policies.
- `POST /policies/global`: Modifies system-wide governance parameters.

### 3. Governance & Audit
- `GET /governance/agent/{agent_id}`: Returns node status metrics.
- `POST /governance/agent`: Registers a new node or updates its metadata status.
- `GET /governance/audit`: Fetches a chronological list of governance events.

### 4. Secure Aggregation
- `POST /secure-aggregation/masks/submit`: Accepts MPC mask shares for a given round.
- `POST /secure-aggregation/masks/aggregate`: Combines mask shares to output the round aggregation mask.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Complete PostgreSQL connection string | Constructed |
| `POSTGRES_HOST` | Database host | `"localhost"` |
| `POSTGRES_PORT` | Database port | `"5432"` |
| `POSTGRES_USER` | Database user | `"user"` |
| `POSTGRES_PASSWORD`| Database password | `"password"` |
| `POSTGRES_DB` | Database name | `"federated_fraud_db"` |

---

## Technology Stack
- **Database Access**: SQLAlchemy Core + ORM (PostgreSQL backend)
- **Framework**: FastAPI, Uvicorn, Pydantic
