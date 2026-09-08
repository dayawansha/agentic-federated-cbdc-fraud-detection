# Final Presentation Slides — MSc Viva/Demonstration
## An Agentic Federated Learning Framework for Privacy Preserving Fraud Detection in CBDC Networks

**Format:** 10 slides · 15-minute talk · followed by 15 min Q&A  
**Candidate:** WAD Dusman Nalin Dayawansha (K2557706) | **Supervisor:** Ms. Karishani Bamunawita

> 📌 **How to use this file:** Each slide has the **slide content** (bullet points for the screen) and a **Speaker Note** block (what you say out loud). Keep slides minimal — you do the talking.

---

## SLIDE 1 — TITLE (30 seconds)

### On Screen
- **Title:** An Agentic Federated Learning Framework for Privacy Preserving Fraud Detection in Central Bank Digital Currency (CBDC) Networks
- **Candidate:** WAD Dusman Nalin Dayawansha — K2557706
- **Supervisor:** Ms. Karishani Bamunawita
- MSc in Data Science, School of Computing — September 2026

> 💬 **Speak:** *"Good [morning/afternoon]. My project is about detecting financial fraud in Central Bank Digital Currency networks — while mathematically guaranteeing that no bank ever has to share its raw customer data with anyone. I'll walk you through the problem, what I designed, how I implemented it, and then demonstrate the live system."*

---

## SLIDE 2 — PROBLEM & MOTIVATION (1.5 minutes)

### On Screen

**The Deadlock:**
> Banks must **collaborate** to see cross-institution fraud chains —  
> but **GDPR & PSD2** forbid sharing raw transaction data.

**Why CBDCs make this urgent:**
- CBDCs are live today — Jamaica, Nigeria, Bahamas; pilots in China, India, Russia
- High-speed programmable payments create new fraud attack surfaces (BIS, 2020)
- No dedicated CBDC fraud detection standard or framework exists yet

**Why existing approaches cannot solve it:**
- Centralised database → violates GDPR data minimisation
- Isolated local bank models → blind to cross-bank fraud chains
- Standard Federated Learning → no graph structure, no privacy layer, no adaptive control

> 💬 **Speak:** *"CBDCs are not a future concept — they are live in multiple countries right now. The Bank for International Settlements has flagged that their programmability and speed make them uniquely vulnerable to coordinated fraud. And the existing toolkit is broken: centralised databases violate privacy law, isolated models miss cross-bank patterns, and off-the-shelf Federated Learning has no mechanism for the graph structure of payments or for handling heterogeneous bank environments. That is the specific gap this research addresses."*

---

## SLIDE 3 — RESEARCH AIM & CORE CONTRIBUTIONS (1 minute)

### On Screen

**Aim:**
> Build an Agentic Federated Learning framework for collaborative CBDC fraud detection — with no raw data ever crossing institutional boundaries.

**Four Core Contributions:**

| # | What Was Built |
|---|---|
| C1 | **Graph-based fraud detection pipeline** — transaction graphs in Neo4j, trained with GNNs locally at each bank |
| C2 | **Privacy-preserving update layer** — Differential Privacy noise + Secure Aggregation (encrypted mask shares escrowed via Policy Manager) |
| C3 | **Agentic Q-Learning engine** — each bank node autonomously adapts its training to local hardware conditions |
| C4 | **Containerised microservice prototype** — full end-to-end Docker Compose deployment with real-time Kafka alerting |

**Literature Gap:**  
No prior study combined GNNs + FL + DP + SecAgg + Agentic AI in a single CBDC fraud framework.

> 💬 **Speak:** *"The aim was not just to apply federated learning to fraud — that exists for conventional banking. The novelty is this specific combination of four technologies, designed from the ground up for CBDC networks, and then actually built and validated as a working system."*

---

## SLIDE 4 — HIGH-LEVEL SYSTEM DESIGN (1.5 minutes)

### On Screen

**Two-tier microservice architecture:**

```
            ┌─────────────────────────────────┐
            │      CENTRAL COORDINATOR NODE   │
            │  Agentic Coordinator (LangGraph)│
            │  Federated Model Aggregator     │
            │  Policy Manager  (ε/δ budgets)  │
            │  Model Registry  (versioned)    │
            └────────────┬────────────────────┘
                         │  HTTP/REST — TLS 1.3
              ┌──────────┼──────────┐
              ▼          ▼          ▼
       ┌───────────┐ ┌───────────┐ ┌───────────┐
       │ Bank Node │ │ Bank Node │ │ Bank Node │
       │ (1..N)    │ │           │ │           │
       └───────────┘ └───────────┘ └───────────┘
       ⛔ Raw transaction data NEVER leaves a Bank Node
```

**Core design principles:**
- **Data locality** — each bank owns its own Neo4j graph and training data
- **Coordinator-blind aggregation** — the coordinator sees only masked, noised updates
- **Governance enforcement** — all privacy budgets (ε, δ) are centrally controlled by the Policy Manager

> 💬 **Speak:** *"The system is split into two tiers. Bank Nodes are where the data lives — they never expose it. The Central Coordinator orchestrates learning rounds but is architecturally prevented from seeing individual bank data — it only ever receives the masked, privatised aggregate. The Policy Manager enforces privacy budgets globally, so no bank node can exceed the allowed epsilon, even if its local agent wanted to."*

---

## SLIDE 5 — BANK NODE INTERNAL DESIGN (1.5 minutes)

### On Screen

**Each Bank Node is a self-contained microservice cluster:**

```
┌─────────────────── BANK NODE ──────────────────────┐
│                                                     │
│  ┌──────────────┐     ┌──────────────┐             │
│  │ Transaction  │────▶│  Neo4j Graph │             │
│  │ Graph (9004) │     │  Database    │             │
│  └──────────────┘     └──────┬───────┘             │
│                              │ features             │
│  ┌──────────────┐     ┌──────▼───────┐             │
│  │ Local Agent  │────▶│  Local GNN   │             │
│  │ (9001)       │     │  Model (9002)│             │
│  │ Q-Learning   │     │  SAGEConv    │             │
│  └──────┬───────┘     │  + GAT       │             │
│         │             └──────┬───────┘             │
│         │ raw gradients      │                     │
│         │        ┌──────────▼───────┐              │
│         └───────▶│  Privacy Layer   │              │
│                  │  (9003)          │              │
│                  │  DP + SecAgg     │              │
│                  └──────┬───────────┘              │
│                         │ masked update            │
│  ┌──────────────┐  ┌────▼──────────┐              │
│  │  Alerting    │  │  → Coordinator│              │
│  │  (9005/Kafka)│  └───────────────┘              │
│  └──────────────┘                                  │
└─────────────────────────────────────────────────────┘
```

**Data flow inside a bank node:**  
Transaction record → Neo4j graph → GNN training → raw gradients → Local Agent → Privacy Layer → masked update out

> 💬 **Speak:** *"Inside each bank node, there are six microservices, each with a clear, single responsibility. The transaction graph service ingests records and builds the Neo4j bipartite graph. The local GNN trains on that graph. The local agent supervises the whole process using Q-learning. The privacy layer applies two layers of protection before anything leaves. And the alerting engine consumes Kafka events to push fraud alerts to operators in real time."*

---

## SLIDE 6 — FEDERATED ROUND SEQUENCE DESIGN (2 minutes)

### On Screen

**The federated learning round has 5 distinct phases:**

**Phase 1 — Initialisation**
- **Agentic Coordinator** fetches global policies (ε, δ) from the **Policy Manager**
- **Agentic Coordinator** health-checks each Bank Node: CPU load, battery, privacy budget remaining
- Only compliant nodes are selected for the round

**Phase 2 — Local Training**
- **Agentic Coordinator** sends a start signal (`round_id + strategy`) to each selected Bank Node
- Bank Node **pulls the latest global weights itself** from the **Model Registry** — Coordinator does not push weights
- Local Agent runs Q-learning: maps hardware state → selects training epochs & noise scale
- GNN trains on the local Neo4j subgraph using the downloaded global weights as starting point

**Phase 3 — Privatisation (inside each Bank Node)**
- **Step 1 — Clip:** Each gradient update is scaled down if it is too large, so no single transaction can have an outsized influence on the model
- **Step 2 — Add Noise:** Controlled random noise is injected into the update — the stronger the privacy required, the more noise is added
- **Step 3 — Mask:** A cryptographic mask is applied so the coordinator can only see the combined total, never any individual bank's update

**Phase 4 — Aggregation**
- **Agentic Coordinator** collects all masked updates → forwards to **Federated Model Aggregator**
- Aggregator cancels pairwise masks, runs **coordinate-wise Median** (Byzantine-robust)
- Validated global model registered in **Model Registry**

**Phase 5 — Inference & Alerting**
- Bank nodes pull new global weights from **Model Registry**
- GNN runs inference on local graph → publishes fraud classifications to Kafka
- Alerting service consumes events → real-time dashboard alerts

> 💬 **Speak:** *"One thing worth clarifying here — when I say 'Coordinator', I always mean the Agentic Coordinator microservice on port 8001, which is the orchestrating brain inside the Central Coordinator Node. It is the service that actively manages the round — fetching policies from the Policy Manager, health-checking bank nodes, and sending updates to the Federated Model Aggregator. These are four separate microservices all living within the Central Coordinator Node, each with a distinct responsibility."*

---

## SLIDE 7 — IMPLEMENTATION: GNN MODEL & GRAPH PIPELINE (1.5 minutes)

### On Screen

| Technology | Purpose |
|---|---|
| **Neo4j 5** | Stores transactions as a bipartite graph (Account → Transaction → Account) and extracts topological features via Cypher |
| **PyTorch 2.1** | Deep learning framework powering local GNN training at each Bank Node |
| **PyTorch Geometric 2.4.0** | GNN layer library — GraphSAGE for scalable neighbourhood aggregation + Graph Attention (GAT) to focus on high-risk relationships |
| **Elliptic++ Dataset** | 203,769 transaction nodes, 234,355 edges — partitioned into 4 temporal shards as proxy for 4 CBDC Bank Nodes |

**GNN Architecture (3 layers):**  
`SAGEConv` → `GATConv (4 attention heads)` → `SAGEConv (classifier)`

**Training approach:** Semi-supervised — label propagation assigns soft pseudo-labels to unlabeled nodes, since less than 1% of transactions carry a known fraud label.

> 💬 **Speak:** *"Neo4j stores the payment graph and computes relational features like degree and transaction velocity. PyTorch Geometric trains the GNN locally at each bank — no data leaves. The three-layer design combines GraphSAGE for scale with Graph Attention to focus on the most suspicious account relationships. Because less than 1% of data is labeled, label propagation is used to extend supervision across the graph."*

---

## SLIDE 8 — IMPLEMENTATION: PRIVACY LAYER (1.5 minutes)

### On Screen

**Two-layer shield — protects model updates before they leave a Bank Node:**

| Layer | Technology | What it does |
|---|---|---|
| **1 — Differential Privacy** | PyTorch (custom microservice) | Clips gradients + injects Gaussian noise → provides **(ε, δ)-DP** mathematical guarantee |
| **2 — Secure Aggregation** | Encrypted mask shares (escrowed in **Policy Manager** PostgreSQL) | Each bank submits an encrypted mask share — aggregator decrypts and combines them to cancel privacy noise → coordinator **cannot reconstruct individual bank updates** |

**Why two layers?**
- DP protects against **membership inference** — inferring individual records from model weights
- SecAgg protects against a **compromised coordinator** — only the aggregate is ever visible

**Governance:** Privacy budgets (ε, δ) are set and enforced centrally by the **Policy Manager** — no bank node can exceed the global cap.

> 💬 **Speak:** *"The privacy layer has two parts that address two different threat models. Differential privacy adds calibrated noise so no individual transaction can be reverse-engineered from the model weights — this is a provable mathematical bound, not a best-effort measure. Secure aggregation works by having each bank encrypt and escrow a mask share with the Policy Manager before the round. The aggregator then retrieves and combines those shares to cancel the masks out — so the coordinator only ever sees the true aggregate, never any individual bank's update."*

---

## SLIDE 9 — IMPLEMENTATION: AGENTIC Q-LEARNING ENGINE (1.5 minutes)

### On Screen

**Each Bank Node is self-governing — the Local Agent decides how to train each round without human intervention.**

| Technology | Role |
|---|---|
| **psutil / pmset** | Monitors real-time CPU load and battery level on the host machine |
| **Tabular Q-Learning** | Maps hardware state → selects training action (simple, interpretable, auditable) |
| **LangGraph 0.0.10** | Models the agent's round lifecycle as a stateful workflow (StateGraph) |
| **Redis 7** | Persists round state — agent resumes from checkpoint on crash/restart |
| **FastAPI** | All inter-service communication (agent ↔ coordinator ↔ GNN) |

**State:** 8 discrete combinations of CPU (high/normal) · Battery (low/normal) · Privacy budget pressure (high/normal)

**Actions the agent can take each round:**
- Decrease training epochs — save energy under hardware pressure
- Increase DP noise scale — tighten privacy near budget cap
- Increase FedProx μ — stabilise model under non-IID data
- Maintain config — when all conditions are normal

> 💬 **Speak:** *"The Q-learning agent is what makes each bank node autonomous. It reads live hardware metrics — CPU from psutil, battery from pmset — combines them with the remaining privacy budget, and maps that to one of 8 states. It then picks one of 4 actions from a Q-table. I used tabular Q-learning rather than a neural policy deliberately — the state space is small enough that a table is fully interpretable and auditable, which matters in a regulated banking context. LangGraph wraps the whole workflow and Redis ensures round state survives any crash."*

---

## SLIDE 10 — CONCLUSION & FUTURE WORK (1 minute)

### On Screen

**What was delivered:**
- ✅ A working, containerised CBDC fraud detection prototype — validated end-to-end
- ✅ Graph-structured federated learning with mathematical (ε, δ)-differential privacy
- ✅ Agentic Q-learning for autonomous, resource-aware training adaptation
- ✅ Coordinator-blind aggregation via Secure Aggregation (encrypted mask shares, Policy Manager escrowed)

**Limitations:**
- No public CBDC transaction dataset exists → evaluated on Elliptic++ (Bitcoin proxy)
- SecAgg masking is O(N²) in the number of nodes — scalability constraint at large N
- Label sparsity (< 1% fraud labels) — mitigated by label propagation, not eliminated

**Three future directions:**

| Direction | Why |
|---|---|
| 🔐 **Homomorphic Encryption (FHE)** | Replace SecAgg — coordinator computations directly on encrypted weights |
| 🏛️ **Real CBDC Ledger Integration** | Test on Hyperledger Fabric or Corda ledger formats |
| ⏱️ **Temporal GNNs (T-GNNs)** | Model time-varying fraud velocity and evolving attack patterns |

> 💬 **Speak:** *"To close — the prototype works. It demonstrates that you can build a collaborative, graph-based fraud detection system for CBDC networks that provides a mathematical privacy guarantee and adapts autonomously to hardware constraints. The main limitation is the absence of public CBDC data, which is a field-wide problem. My top priority for future work is homomorphic encryption, because it would eliminate the O(N²) scaling problem of SecAgg while keeping the coordinator blind — which is the fundamental design requirement."*

---

## Q&A PREPARATION — NOT A SLIDE

> Study these before the viva. These cover the design and implementation depth the examiners will probe.

---

**Q: Walk me through the bipartite graph schema — why Account and Transaction as separate node types?**  
A: In Bitcoin's UTXO model, edges connect transactions to transactions. In CBDC and account-based systems, money flows between accounts via discrete payment events. Separating Account and Transaction as distinct node types maps directly to that model — it lets the GNN learn account-level risk scores and transaction-level anomaly scores independently. The SAGEConv layers aggregate neighbourhood signals from both node types.

**Q: Why GraphSAGE and GAT together — why not just one?**  
A: SAGEConv handles scalable neighbourhood sampling — essential for large bank graphs with millions of accounts. GAT adds attention weights so the model can learn to focus on high-risk edges (e.g., edges to known fraudulent accounts). They complement each other: SAGE for breadth, GAT for focused attention on suspicious relationships.

**Q: How does the Q-learning agent decide what reward to assign to an action?**  
A: The reward function balances three signals: the local F1-score improvement from the round (positive reward), the energy cost of the training run (negative reward for high consumption), and a penalty if the privacy budget is overspent. This creates a three-way trade-off — the agent cannot optimise one at the expense of the others.

**Q: Why LangGraph for the agent workflow — why not a simple state machine in Python?**  
A: LangGraph provides stateful persistence out of the box via Redis — if the coordinator crashes mid-round, the workflow resumes from the last persisted state rather than starting over. It also gives us clean graph-based transition logic with timeout policies and retry semantics. A plain Python state machine would require rebuilding all of that manually.

**Q: Does the Local Agent break the differential privacy guarantee by adjusting ε?**  
A: No. The agent cannot raise ε above the global cap enforced by the Policy Manager. It can only tighten privacy — reducing ε or increasing noise — within the governance boundary. Every action is logged and auditable. The mathematical guarantee is always preserved.

**Q: How does the Robust Median aggregation defend against a poisoned bank node?**  
A: Coordinate-wise median takes the median value at each weight position across all submitted updates. A poisoned or Byzantine node would need to corrupt more than half the participating nodes to shift the median — which is practically infeasible in a regulated banking environment where node identities are verified.

**Q: What happens if a bank node drops out mid-round?**  
A: The coordinator uses `asyncio.wait_for` with a configurable timeout (`ROUND_WAIT_SECONDS`). If a node times out, its update is discarded and the round completes with the responsive subset. The LangGraph state machine performs compensating logic — rather than a full rollback, it proceeds with clean updates, which is logged in the audit trail.

**Q: How does Secure Aggregation work in practice — how do the masks cancel?**  
A: Before training, each bank generates an encrypted mask share and escrows it with the Policy Manager (stored in the `secure_aggregation_masks` PostgreSQL table). After all banks submit their privatised model updates, the Federated Model Aggregator calls the Policy Manager to retrieve and decrypt those shares. It then combines them into an aggregate cancellation mask and applies it to remove the individual noise — leaving only the true gradient sum. The coordinator never holds any individual bank's unmasked update at any point.

---

*Viva Preparation Document — MSc Final Assessment, September 2026*
