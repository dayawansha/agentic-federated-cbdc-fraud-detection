%%{init: {"theme":"base","themeVariables":{
  "primaryColor":"#EAF3FF",
  "primaryBorderColor":"#1F3B67",
  "primaryTextColor":"#111827",
  "lineColor":"#1F3B67",
  "signalColor":"#1F3B67",
  "signalTextColor":"#111827",
  "actorBkg":"#F8FAFC",
  "actorBorder":"#334155",
  "actorTextColor":"#111827",
  "noteBkgColor":"#FFF7ED",
  "noteTextColor":"#111827",
  "noteBorderColor":"#9A3412",
  "tertiaryColor":"#F1F5F9",
  "tertiaryBorderColor":"#475569",
  "tertiaryTextColor":"#111827",
  "textColor":"#111827",
  "fontFamily":"Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"
}}}%%

sequenceDiagram
    autonumber

    %% Core ledger / streaming participants
    participant CBDC as CBDC Core / Payment Rail
    participant TG as transaction-graph (9004)
    participant N4J as Neo4j DB
    participant KF as Kafka Bus
    participant AL as alerting (9005)
    participant FD as fraud-dashboard (3001)

    %% Local bank node training services
    participant LA as local-agent (9001)
    participant LG as local-gnn (9002)
    participant PL as privacy-layer (9003)

    %% Central coordinator & compliance services
    participant AC as agentic-coordinator (8001)
    participant SA as federated-model-aggregator (8002)
    participant PM as policy-manager (8003)
    participant MR as model-registry (8004)

    rect rgb(248, 250, 252)
        Note over CBDC, AL: Phase 1: Real-time Ingestion, Rule-Based Alerting, and Change Data Capture (CDC)
        CBDC->>TG: POST /transactions (transaction_id, source, target, amount, asset_type)
        TG->>N4J: Write transaction node and relationships
        TG-->>CBDC: 200 OK (success=True)
        TG->>KF: Publish CDC event to topic: transactions.events
        
        AL->>KF: Consume from topic: transactions.events
        AL-->>AL: Evaluate rules (amounts > $10K/$50K, velocity repeats, self-transfers)
        alt Rule triggered (risk score >= 0.5)
            AL->>KF: Publish generated alert event to topic: fraud.alerts
        end

        AL->>KF: Consume from topic: fraud.alerts (both rule & GNN alerts)
        AL-->>AL: Persist AlertRecord in PostgreSQL
        AL-->>AL: Dispatch notifications (Slack webhook, Email, SMS)
        AL-->>FD: Broadcast alert payload via WebSocket: /ws/alerts
    end

    rect rgb(255, 251, 245)
        Note over FD, LA: Phase 2: Live UI Dashboard Monitoring & Status Polling
        loop Every 5 seconds (Dashboard polling)
            FD->>LA: GET /agent/status
            LA-->>FD: Return last round metrics, local status, CPU/Battery constraints
            FD->>AL: GET /alerts/recent?limit=50
            AL-->>FD: Return list of recent alert tickets
            FD->>AL: GET /alerts/summary
            AL-->>FD: Return severity charts and counts of open issues
        end
    end

    rect rgb(240, 253, 244)
        Note over AC, MR: Phase 3: Federated Learning Round Initialization & Governance check
        AC->>PM: GET /policies/global (Fetch round policies)
        PM-->>AC: Return policy rules (min_agents, allowed_assets, reliability threshold)
        AC->>MR: GET /models/latest (Fetch latest global GNN baseline)
        MR-->>AC: Return version metadata and storage paths (artifact_path)
        
        loop Active Agent Selection Gating (Iterate over config node URLs)
            AC->>LA: GET /health (Heartbeat checks)
            LA-->>AC: Return healthy status
            AC->>PM: GET /governance/agent/{agent_id} (Check compliance)
            PM-->>AC: Return active flag, reliability score, and asset eligibility
            AC->>PM: GET /policies/budget/{agent_id} (Verify privacy reserve)
            PM-->>AC: Return remaining privacy budgets (epsilon, delta balance)
        end
        AC-->>AC: Compile list of compliant and healthy bank nodes
    end

    rect rgb(244, 244, 249)
        Note over AC, PL: Phase 4: Local GNN Training & Adaptive Execution (Bank Node Pipeline)
        AC->>LA: POST /agent/round/start (round_id, strategy, parameters)
        activate LA
        LA->>LA: Check local CPU load (reject if >90%) and battery level (reject if <20%)
        LA->>PM: GET /policies/budget/{agent_id} (Verify privacy balance is sufficient)
        PM-->>LA: Return budget details
        LA-->>LA: Run adaptive local planning (epoch scaling and noise choices)
        LA->>MR: GET /models/{version_id}/weights (Download GNN weights)
        MR-->>LA: Return base64 weights payload
        LA->>TG: GET /graph/export-tensors (Extract graph structure)
        TG->>N4J: Query graph topology, degree metrics, and feature lists
        N4J-->>TG: Graph datasets
        TG-->>LA: Return formatted node tensors & edge indices
        LA->>LG: POST /train (Pass weights, datasets, epochs, pseudo-label parameters)
        LG-->>LG: Train PyTorch Geometric GNN (runs semi-supervised pseudo-labeling)
        LG-->>LA: Return newly trained GNN weights & local accuracy/loss metrics
        LA->>PL: POST /privacy/clip-gradients (Cap extreme training steps)
        PL-->>LA: Return normalized gradients
        LA->>PL: POST /privacy/apply-dp (Apply Gaussian noise camouflage)
        PL-->>LA: Return Differential Privacy weights
        LA->>PL: POST /privacy/prepare-secure-update (Create zero-sum masks)
        PL->>PM: GET /secure-aggregation/escrow/public-key
        PM-->>PL: Return escrow X25519 public key
        PL-->>PL: Mask weights and encrypt mask share
        PL-->>LA: Return masked_weights and encrypted_mask_share
        LA->>PL: POST /privacy/encrypt (Apply transport symmetry encryption)
        PL-->>LA: Return ciphertext payload
        LA->>AC: POST /updates/submit (Submit ciphertext model, metrics, and mask share)
        deactivate LA
        AC->>PM: POST /secure-aggregation/masks/submit (Escrow the mask share)
        PM-->>AC: Confirm stored
    end

    rect rgb(254, 242, 242)
        Note over AC, LG: Phase 5: Weight Consensus, Decryption, and Global Aggregation
        AC->>AC: Wait for all selected agents to submit or timeout
        
        loop Weight Negotiation
            AC->>LA: POST /agent/negotiate/propose-weights (Propose partner weights)
            LA-->>AC: Return proposals based on peer reliability and sample sizes
        end
        AC-->>AC: Aggregate votes and verify consensus weight ratios
        
        AC->>PM: POST /secure-aggregation/masks/aggregate (Reconstruct mask cancellation)
        PM->>PM: Decrypt all mask shares using escrow private key
        PM-->>AC: Return combined round cancelation mask
        
        AC-->>AC: Decrypt updates and subtract round cancelation mask
        AC->>SA: POST /aggregate (Combine weights via FedAvg, FedProx, or RobustMedian)
        SA-->>AC: Return aggregated global weights & global validation metrics
        
        AC->>MR: POST /models/register (Save new global model version)
        MR->>MR: Store model checkpoint file, upload to S3/MinIO, log to MLflow
        MR-->>AC: Return registered version_id
        
        loop Update Privacy Budgets
            AC->>PM: POST /policies/budget/update (Deduct spent epsilon/delta)
            PM-->>AC: Return success
        end
        AC-->>AC: Round complete
        
        Note over LA, LG: Phase 6: Post-Round Local GNN Inference & Alert Dispatch
        LA->>MR: GET /models/latest/weights (Download fresh global model)
        MR-->>LA: Return weights
        LA->>LG: POST /infer (Evaluate local transaction graph)
        LG-->>LA: Return risk predictions list
        loop Publish high-risk predictions
            LA->>KF: Publish prediction details to topic: fraud.alerts
        end
    end
