# Policy Manager

Governance, compliance auditing, privacy limit enforcement (ε, δ), and secure aggregation mask tracking.

## Port
- **`8003`** (REST API)

## Service Responsibilities
The `policy-manager` acts as the system's compliance officer and security guard. It enforces privacy boundaries, manages system settings, monitors bank node health, and keeps a detailed audit trail of all coordination events.

1. **Privacy Protection (Privacy Limit Management)**
   - **What it does:** Ensures that no bank leaks sensitive, private customer data during the AI training process.
   - **How it works:** Every time a bank trains the AI model, a small amount of the allowed "privacy limit" (measured using parameters called Epsilon $\epsilon$ and Delta $\delta$) is consumed. The Policy Manager tracks this usage and blocks any bank that is exceeding its limit to prevent data leaks.

2. **Setting System Rules (System Governance)**
   - **What it does:** Stores and manages the global settings for how the system operates.
   - **How it works:** It controls system-wide settings, such as the minimum number of banks required to start a training round and the quality/accuracy targets the AI models must meet.

3. **Monitoring Bank Reliability (Node Lifecycle & Reliability)**
   - **What it does:** Keeps track of which banks are actively participating and how reliable they are.
   - **How it works:** It registers new bank nodes when they join. If a bank node is slow, has poor internet connection, or fails to complete its tasks, the Policy Manager lowers its reliability score.

4. **Keeping a Permanent Log Book (Audit Logging)**
   - **What it does:** Records a detailed history of everything that happens for compliance and security audits.
   - **How it works:** It writes down critical events (such as when a new bank registers, when policies change, or when privacy limits are adjusted) to a database so there is an untampered paper trail.

5. **Coordinating Secret Keys (Secure Aggregation Coordination)**
   - **What it does:** Helps blend everyone's AI models together securely without letting the coordinator see any bank's individual data.
   - **How it works:** Banks hide their local updates using mathematical "masks" (like temporary passwords). The Policy Manager collects pieces of these masks and combines them so that the coordinator can decrypt the final merged model without ever being able to decrypt any individual bank's model.
   - **Why it is here (Separation of Duties / Security Boundary):**
     In cryptographic federated learning designs, a common threat model involves a *semi-honest coordinator*.
     * **The Risk:** If a single component receives the banks' individual encrypted/masked model updates *and* collects/reconstructs the individual secret mask shares, a compromise of that single service exposes all individual bank datasets.
     * **The Solution:** By separating the key escrow service (`policy-manager`) from the parameter merging service (`federated-model-aggregator`), we divide the trust boundary. Under a production deployment, these two services could be run in different security zones, with separate network accessibility profiles, or even managed by different administrative entities. The `policy-manager` acts as the stateful key escrow and coordination layer, keeping the compute-heavy `federated-model-aggregator` stateless and isolated from sensitive keys.


---

## API Endpoints

### 1. Privacy Limits
- `GET /policies/budget/{agent_id}`: Fetches the current and maximum privacy limit (Epsilon, Delta) for an agent.
- `POST /policies/budget/update`: Subtracts Epsilon/Delta usage for an agent after a round.
- `POST /policies/budget/set`: Initializes or forces a custom privacy limit config for an agent.

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
