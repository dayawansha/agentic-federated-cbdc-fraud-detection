# FACULTY OF ENGINEERING AND COMPUTING  
## School of Computing MSc. DEGREE IN DATA SCIENCE  

**Name:** WAD Dusman Nalin Dayawansha  
**ID Number:** K2557706  
**Project Title:** An Agentic Federated Learning Framework for Privacy Preserving Fraud Detection in Central Bank Digital Currency (CBDC) Networks  
**Supervisor:** Ms. Karishani Bamunawita  
**Date:** 30.01.2026  

---

# I. WARRANTY STATEMENT  

This is a student project. Therefore, neither the student nor University makes any warranty, express or implied, as to the accuracy of the data or conclusion of the work performed in the project and will not be held responsible for any consequences arising out of any inaccuracies or omissions therein.  

---

# II. DECLARATION  

I, WAD Dusman Nalin Dayawansha, declare that this dissertation titled "An Agentic Federated Learning Framework for Privacy Preserving Fraud Detection in Central Bank Digital Currency (CBDC) Networks" is my own work and has not been submitted previously for any other degree or professional qualification. All sources and literature referenced herein have been explicitly acknowledged.

---

# III. DEDICATION  

*To my parents, family, and supervisor, whose constant support and guidance made this research possible.*  

---

# IV. ACKNOWLEDGEMENT  

I would like to express my deepest gratitude to my academic supervisor, **Miss Karishani Bamunawita**, for her invaluable guidance, technical insights, and continuous encouragement throughout this project. 

I also extend my sincere thanks to the faculty of the School of Computing at Kingston University for providing the academic foundations required to undertake this research. Finally, I am grateful to my family and friends for their understanding and support during the course of my MSc studies.

---

# V. TABLE OF CONTENT  

**Catalog**

| Section | Description | Page |
| :--- | :--- | :--- |
| **I** | [WARRANTY STATEMENT](#i-warranty-statement) | i |
| **II** | [Declaration](#ii-declaration) | i |
| **III** | [Dedication](#iii-dedication) | i |
| **IV** | [Acknowledgement](#iv-acknowledgement) | i |
| **V** | [Table of Content](#v-table-of-content) | i |
| **VI** | [Glossary of Terms](#vi-glossary-of-terms) | iv |
| **VII** | [Abstract](#vii-abstract) | v |
| **VIII** | [Introduction](#viii-introduction) | 1 |
| | ↳ [A. Prolegomena](#a-prolegomena) | 1 |
| **IX** | [Aim and Objectives](#ix-aim-and-objectives) | 1 |
| | ↳ [A. Aim](#a-aim) | 1 |
| | ↳ [B. Objectives](#b-objectives) | 1 |
| | ↳ [C. Background and Motivation](#c-background-and-motivation) | 2 |
| | ↳ [D. Problem in Brief](#d-problem-in-brief) | 2 |
| | ↳ [E. Proposed Solution](#e-proposed-solution) | 3 |
| | ↳ [F. Structure of the Thesis](#f-structure-of-the-thesis) | 3 |
| | ↳ [G. Summary](#g-summary) | 4 |
| **X** | [Literature Review](#x-literature-review) | 4 |
| | ↳ [A. Introduction](#a-introduction) | 4 |
| | ↳ [B. Evolution of Graph Learning and Fraud Analytics](#b-evolution-of-graph-learning-and-fraud-analytics) | 4 |
| | ↳ [C. Privacy Preserving Machine Learning](#c-privacy-preserving-machine-learning) | 4 |
| | ↳ [D. Agentic AI for Adaptive Federated Coordination](#d-agentic-ai-for-adaptive-federated-coordination) | 5 |
| | ↳ [E. Problem Definition and Literature Gap](#e-problem-definition-and-literature-gap) | 5 |
| | ↳ [F. Summary](#f-summary) | 6 |
| **XI** | [TECHNOLOGY](#xi-technology) | 6 |
| | ↳ [A. Selection Justification](#a-selection-justification) | 6 |
| | ↳ [B. Graph Processing & ML Stack](#b-graph-processing--ml-stack) | 7 |
| | ↳ [C. Streaming & Storage Infrastructure](#c-streaming--storage-infrastructure) | 7 |
| **XII** | [DESIGN](#xii-design) | 7 |
| | ↳ [A. High-Level System Architecture](#a-high-level-system-architecture) | 7 |
| | ↳ [B. System Architecture](#b-system-architecture) | 8 |
| | ↳ [C. System Interaction Flow (Sequence Flow)](#c-system-interaction-flow-sequence-flow) | 10 |
| **XIII** | [APPROACH](#xiii-approach) | 13 |
| | ↳ [A. Transaction Representation & Data Modeling](#a-transaction-representation-&-data-modeling) | 13 |
| | ↳ [B. Proxy Dataset Description and Data Preparation](#b-proxy-dataset-description-and-data-preparation) | 14 |
| | ↳ [C. Dynamic Feature Engineering](#c-dynamic-feature-engineering) | 14 |
| | ↳ [D. GNN-based Semi-Supervised Learning & Label Propagation](#d-gnn-based-semi-supervised-learning-&-label-propagation) | 15 |
| | ↳ [E. Collaborative Federated Optimization](#e-collaborative-federated-optimization) | 15 |
| **XIV** | [IMPLEMENTATION](#xiv-implementation) | 15 |
| | ↳ [A. Local Agent Resource Profiler & Q-Learning Engine](#a-local-agent-resource-profiler-&-q-learning-engine) | 16 |
| | ↳ [B. Dataset Ingestion and Neo4j Database Pipeline](#b-dataset-ingestion-and-neo4j-database-pipeline) | 16 |
| | ↳ [C. Graph Database Feature Indexing Pipeline](#c-graph-database-feature-indexing-pipeline) | 17 |
| | ↳ [D. PyTorch Geometric Model & Training Pipeline](#d-pytorch-geometric-model-&-training-pipeline) | 17 |
| | ↳ [E. Privacy Layer (DP Noise & X25519 Masking)](#e-privacy-layer-dp-noise-&-x25519-masking) | 18 |
| | ↳ [F. Agentic Coordinator & Robust Aggregator](#f-agentic-coordinator-&-robust-aggregator) | 19 |
| **XV** | [EVALUATION](#xv-evaluation) | 20 |
| | ↳ [A. Experimental Setup & Datasets](#a-experimental-setup-&-datasets) | 20 |
| | ↳ [B. Fraud Detection Performance Analysis](#b-fraud-detection-performance-analysis) | 20 |
| | ↳ [C. Agentic Resource-Aware Performance](#c-agentic-resource-aware-performance) | 20 |
| | ↳ [D. Privacy Budget (Epsilon) Decay and Noise Impact](#d-privacy-budget-epsilon-decay-and-noise-impact) | 21 |
| **XVI** | [CONCLUSION AND FUTURE WORK](#xvi-conclusion-and-future-work) | 21 |
| | ↳ [A. Summary of Contributions](#a-summary-of-contributions) | 21 |
| | ↳ [B. Limitations](#b-limitations) | 21 |
| | ↳ [C. Future Work](#c-future-work) | 22 |
| **XVII** | [REFERENCES](#xvii-references) | 22 |

---

# VI. GLOSSARY OF TERMS

*   **AI** — Artificial Intelligence
*   **CBDC** — Central Bank Digital Currency
*   **FL** — Federated Learning
*   **GNN** — Graph Neural Network
*   **ML** — Machine Learning
*   **API** — Application Programming Interface
*   **CDC** — Change Data Capture
*   **DP** — Differential Privacy
*   **GAT** — Graph Attention Network
*   **GDPR** — General Data Protection Regulation
*   **gRPC** — Remote Procedure Call framework
*   **mTLS** — Mutual Transport Layer Security
*   **PSD2** — Payment Services Directive 2
*   **RL** — Reinforcement Learning
*   **Non-IID** — Non-Independent and Identically Distributed Data
*   **FedAvg** — Federated Averaging Algorithm

---

# VII. ABSTRACT  

Digital currencies like Bitcoin, Ethereum, and Tether have become a major global medium of exchange. However, their rise highlights a key challenge: these currencies cannot be governed or controlled by central banks because they are non-sovereign digital assets. In response, several countries are introducing or developing Central Bank Digital Currencies (CBDCs) as sovereign alternatives. Yet, fraud remains a persistent issue in any digital currency environment. This research proposes an Agentic Federated Learning framework designed specifically to detect fraud in CBDC networks without compromising user privacy.

The framework allows financial institutions to train Graph Neural Network (GNN) models collaboratively without sharing or exposing raw transaction data, ensuring compliance with privacy regulations like GDPR. By combining federated learning with differential privacy, secure aggregation, and agentic AI, the system supports autonomous coordination, robust update aggregation, and training that adapts to the resource constraints (like CPU and battery) of individual nodes. The prototype was evaluated using the Elliptic++ dataset as a proxy for CBDC transaction streams. The results show that the federated GNN model achieves detection performance close to centralized baselines while keeping strict mathematical privacy budgets.

---


# VIII. INTRODUCTION  

## A. Prolegomena  
Sovereign Central Bank Digital Currencies (CBDCs) are transforming the global retail and wholesale payment landscapes. By introducing programmable digital cash issued directly by monetary authorities, CBDC architectures promise faster settlements and lower cross-border transfer fees. However, this high-velocity digital rails environment also exposes the financial ecosystem to rapid, sophisticated fraud schemes, requiring robust monitoring and security architectures tailored to digital currency ecosystems (Malkoochi, 2025). 

According to reports from the Bank for International Settlements (BIS), the programmability and transaction speed of digital currencies make them highly vulnerable to coordinated multi-hop transaction chaining and structured money laundering. 

Historically, fraud detection has relied on rule-based transaction checks or centralized database collation. Centralized databases, however, create significant regulatory compliance liabilities, as pooling customer transaction records across different banks violates the "data minimization" principles of the General Data Protection Regulation (GDPR) and the strict data isolation mandates of the Payment Services Directive 2 (PSD2). 

While some researchers have tried deploying machine learning models directly on isolated bank nodes, local models remain blind to relational networks that cross institutional boundaries. Consequently, commercial banks struggle to flag fraud chains that hop across different institutions. 

This thesis addresses the core conflict between regulatory privacy compliance and collaborative intelligence in CBDC systems. An **Agentic Federated Learning Framework** is presented, combining localized Graph Neural Networks (GNNs), zero-sum secure aggregation, and autonomous reinforcement-learning-guided agents. 

The resulting framework allows financial institutions to identify network-wide fraud patterns collaboratively while keeping raw transaction data strictly isolated on their own nodes.

# IX. AIM AND OBJECTIVES  

## A. Aim  
To develop an Agentic Federated Learning framework that enables privacy-preserving, adaptive, and collaborative fraud detection across Central Bank Digital Currency (CBDC) ecosystems without requiring institutions to share sensitive transaction data.

## B. Objectives  
1) *To Develop a Federated Learning Framework for CBDC Fraud Detection.*  
To Develop a Federated Learning Framework for CBDC Fraud Detection that enables a distributed learning setup in which each institution trains a local model without sharing raw transaction data, thereby ensuring privacy and regulatory compliance. 

2) *To Develop Agentic AI Capabilities*  
To develop agentic components capable of managing training rounds, monitoring model behavior, and adapting the learning workflow with minimal human intervention. 

3) *To Develop a Privacy-Preserving Training Pipeline*  
To develop privacy-preserving mechanisms such as encrypted model updates, differential privacy, or secure aggregation to ensure sensitive CBDC transaction data is never exposed. 

4) *To Develop a Prototype*  
To develop a working prototype demonstrating how federated learning and agentic coordination can jointly detect fraud in a privacy-preserving CBDC-like environment. 

5) *SMART Objectives*  
*   **Specific:** Implement a federated GNN-based fraud detection prototype.  
*   **Measurable:** Evaluate performance using Precision, Recall, F1-score, and ROC-AUC against centralized baselines.  
*   **Achievable:** Use synthetic and open-source datasets for simulation (such as the Elliptic++ dataset) for transaction simulation.  
*   **Relevant:** Address privacy and compliance challenges in CBDC systems.  
*   **Time-bound:** Complete design, implementation, and evaluation within the project timeline.  

## C. Background and Motivation  
Sovereign Central Bank Digital Currencies (CBDCs) are fundamentally reshaping how money works at a national level. This is no longer just a theoretical framework. Jamaica, Nigeria, and the Bahamas have already launched live CBDCs, and larger economies like China, India, Russia, etc. are running active pilot programs. That shift from concept to real-world deployment brings distinct payment security challenges.

The primary challenge is that fraud detection has not kept pace with the rapid deployment of these digital payment systems. Traditionally, fraud monitoring has required pulling transaction records from multiple banks into one central clearinghouse or registry, where models and analysts could inspect the data for suspicious activity. That approach faces two major obstacles. First, privacy regulations like GDPR and PSD2 place tight restrictions on sharing raw customer data. Second, even setting regulation aside, banks are generally reluctant to share their transaction records because they treat that data as a competitive asset, rather than a resource to be pooled with rivals.

Federated Learning (FL) offers a resolution to this deadlock. Rather than centralizing data, FL allows banks to keep their records local and share only model weight updates. Pairing that with Graph Neural Networks (GNNs), which represent accounts and transactions as nodes and edges in a network, enables the system to capture relational patterns that traditional tabular models—the kind banks have relied on for years—cannot fully detect.

However, conventional FL frameworks have a blind spot: they assume every node operates in a clean, uniform environment. In practice, banking infrastructures are highly heterogeneous. Some nodes deal with heavy CPU loads, others hit resource constraints during peak hours, and the volume of labeled data varies enormously from one institution to the next.

That gap is exactly what motivates this research: building an agentic layer that can dynamically tune hyperparameters and training intensity at the local level. This approach enables federated learning to transition from controlled simulations to practical commercial deployments.

## D. Problem in Brief  
Central Bank Digital Currencies (CBDCs) are a new frontier in finance, but no standardized fraud detection systems exist for CBDC ecosystems yet. As a result, early pilots and deployments lack dedicated security frameworks and remain exposed to sophisticated financial crime.

Collaborative fraud detection is further blocked by data privacy constraints: banks training isolated models cannot detect transaction patterns or transfer chains that traverse multiple institutions, leaving fraud detection incomplete across the network.

This thesis addresses these challenges by introducing an agentic Federated Learning (FL) framework for multi-institution collaboration without data sharing, combined with privacy-preserving techniques to protect sensitive transactional data.

## E. Proposed Solution  
A microservice architecture is utilized to partition execution between individual **Bank Nodes** (the client training sites) and a **Central Coordinator Node** (the aggregation and orchestration hub).

Each **Bank Node** operates as an independent microservice cluster containing the following components:
*   **Transaction Graph (Neo4j):** The transaction-graph is the data structure manager (graph builder) of the bank node. It converts standard flat transaction records into interconnected network maps (graphs) and stores them.
*   **Local Agent:** Serves as the local manager (supervisor) of the bank node, controlling local tasks inside the bank and communicating with the central coordinator to run the local training cycle (Autonomous Round Workflow), negotiate training weights (Weight Negotiation), vote on system rules (Consensus & Pattern Evaluation), and monitor alarms (Inference Monitoring).
*   **Local GNN Model:** The local-gnn-model is the AI engine (analytical brain) of the bank node. It is responsible for training the machine learning models and detecting suspicious activity on the bank's transaction graph.
*   **Privacy Layer:** The privacy-layer is the security shield of the bank node. It ensures that the bank's AI learnings are completely safe and scrambled before they are sent over the network to the central coordinator.
*   **Fraud Dashboard:** The fraud-dashboard is the dashboard (control screen) of the system. It is the visual website/interface that bank operators use to see live fraud alerts and watch the training metrics.
*   **Alerting/Notification Engine:** A message consumer connected to Kafka topics that logs high-risk events in PostgreSQL and triggers instant alerts (such as Email/Tickets).

The **Central Coordinator Node** orchestrates the collaborative learning cycle through the following services:
*   **Agentic Coordinator:** Acts as the conductor (brain) of the entire federated system, managing training rounds (Federated Round Orchestration), handling system failures (SAGA Orchestration Pattern), voting on fraud patterns (Consensus & Threat Intelligence), and integrating system-wide services.
*   **Secure Aggregator:** The federated-model-aggregator is the merging engine (math brain) of the system. It combines all the separate models trained by individual banks into a single, improved global model.
*   **Policy Manager:** Governs system privacy budgets ($\epsilon$, $\delta$), tracks audit trails, and distributes global execution policies.
*   **Model Registry:** Stores versioned global models and synthetic evaluation metadata.

## F. Structure of the Thesis  
This thesis has been structured with 8 chapters:
Chapter 1: Introduction presents aiming objectives, problem statements, and the high-level proposed solution.
Chapter 2: Literature Review analyzes GNN architectures, federated learning paradigms, privacy mechanisms, and identifies research gaps.
Chapter 3: Technology justifies the tools selected, including PyTorch Geometric, Neo4j, Kafka, and FastAPI.
Chapter 4: Design describes architectural block diagrams, service boundaries, and sequence flows.
Chapter 5: Approach details feature engineering, semi-supervised GNN logic, and the secure federated learning cycle.
Chapter 6: Implementation outlines code segments, Q-learning updates, gradient privatization, and Secure Aggregation masks.
Chapter 7: Evaluation presents experimental performance metrics, training curves, privacy decay, and resource savings.
Chapter 8: Conclusion and Future Work summarizes accomplishments and suggests future research directions.

## G. Summary  
This chapter introduced the research scope, outlining the conflict between data privacy regulations and collaborative fraud detection in CBDC payment rails. SMART research objectives were established, aiming to build a prototype GNN federated framework managed by agentic actors. 

The next chapter provides a detailed critical review of the solutions.

---


# X. LITERATURE REVIEW

## A. Introduction
The previous section introduced the research background, problem, and objectives. This section reviews the literature related to graph machine learning, federated learning, privacy-preserving analytics, and agentic AI. It examines the evolution, major developments, and limitations of these technologies, as well as their relevance to fraud detection in Central Bank Digital Currency (CBDC) networks. Based on this review, the research gap addressed by the proposed framework is identified.

## B. Evolution of Graph Learning and Fraud Analytics
Early fraud-detection systems used predefined rules to flag suspicious activities, such as unusually large or frequent transactions. Although easy to understand and audit, these systems often failed to detect organised fraud techniques such as smurfing, where large amounts are divided into smaller transactions to avoid detection.

Machine-learning models such as Random Forest and XGBoost improved fraud detection by analysing transaction features, including amount, account balance, location, and frequency. However, treating transactions as independent records overlooked the relationships among accounts. Graph-based methods addressed this limitation by representing accounts as nodes and transactions as edges. While early methods used manually extracted features such as PageRank and degree centrality, Graph Neural Networks (GNNs) learned directly from the graph structure.

Major developments included Graph Convolutional Networks (GCNs) by Kipf and Welling (2017), GraphSAGE by Hamilton et al. (2017), and Graph Attention Networks (GATs) by Veličković et al. (2018). These models support the detection of coordinated transactions and suspicious fund flows. However, most GNN-based methods assume centralised access to the complete transaction graph, which is impractical when data are distributed across banks and protected by privacy and regulatory requirements. This limitation motivates the privacy-preserving approaches discussed in Section X-C.

## C. Privacy Preserving Machine Learning
Federated Learning (FL), introduced by McMahan et al. (2017), enables multiple organisations to train a shared model without exchanging raw data. Each client trains the model locally and sends model updates to a coordinating server, which commonly uses Federated Averaging to produce an improved global model. This makes FL suitable for collaboration among banks while allowing transaction data to remain within each institution.

However, model updates may still reveal sensitive training information through membership-inference and data-reconstruction attacks. Differential Privacy (DP) reduces this risk by limiting the influence of individual records and adding controlled noise to model updates (Dwork & Roth, 2014; Abadi et al., 2016). Stronger noise improves privacy but may reduce model accuracy.

Secure Aggregation provides additional protection by allowing the server to combine client updates without viewing them individually (Bonawitz et al., 2017). Together, FL, DP, and Secure Aggregation provide a strong privacy-preserving foundation, although they introduce additional communication, computational, and coordination costs.

## D. Agentic AI for Adaptive Federated Coordination
The privacy-preserving techniques discussed in Section X-B often use fixed training settings for all clients. However, banks may differ in their computing resources, network conditions, data volumes, fraud-label availability, and privacy requirements. Therefore, a fixed configuration may not be suitable for every institution.

Previous research has explored adaptive client selection. For example, the Oort system proposed by Lai et al. (2021) selects participants according to their statistical utility and system performance. Agentic AI could extend this approach by monitoring local conditions and selecting approved actions, such as adjusting training epochs, delaying participation during high system load, or opting out of a federated round.

Such decisions could be supported by reinforcement learning to balance model performance, resource usage, privacy, and training time. However, existing research mainly focuses on client selection and efficiency rather than the privacy–performance requirements of fraud detection. Agent decisions must therefore remain within predefined privacy limits and be explainable, auditable, and governed by institutional policies. Defining these safe decision boundaries remains an open research problem.

## E. Problem Definition and Literature Gap
Most previous studies have focused on fraud detection in traditional financial systems, including commercial banking, credit-card payments, and other conventional digital-payment networks. Within these contexts, GNNs, Federated Learning, Differential Privacy, Secure Aggregation, and adaptive or agentic coordination have generally been examined separately. However, this literature review did not identify a study that integrates these technologies into a single fraud-detection framework designed specifically for CBDC networks.

**Emerging CBDC fraud-detection research:** CBDCs remain a relatively new development, and only a small number of countries have fully deployed them. Most CBDC research has focused on monetary policy, financial stability, system architecture, cybersecurity, privacy, and regulatory requirements (BIS, 2020; BIS CPMI, 2021; BIS CGRM, 2023). Although some recent studies have proposed frameworks for improving CBDC security and fraud monitoring (e.g., Malkoochi, 2025), this field remains at an early stage. In particular, there is limited evidence of fraud-detection models being trained and validated using real-world, labelled CBDC transaction data.

The limited availability of operational CBDC data presents an important research challenge. Existing financial fraud-detection studies usually rely on credit-card, conventional banking, cryptocurrency, or synthetic datasets. These datasets may not fully represent the transaction volume, programmability, governance structure, and emerging fraud patterns of CBDC networks.

**Addressing the Data Gap with Proxy Ledger Data:** To bridge the operational data gap, this research utilizes a modified version of the **Elliptic++ dataset** (Monnerat et al., 2023), which is a real-world graph network of Bitcoin blockchain transactions and wallet addresses. Since sovereign CBDC transaction datasets are not publicly accessible due to strict bank secrecy and national security policies, Bitcoin blockchain data (which shares transactional features and graph structure with potential distributed CBDC payment rails) is utilized as a proxy. To evaluate the decentralized and federated nature of the proposed framework, the unified Elliptic++ dataset is modified: it is partitioned temporally into multiple sub-graphs (shards) representing distinct financial institutions, features are standardized, and local structural graph metrics are dynamically computed to simulate distributed bank node datasets. This allows validation of a federated GNN model on realistic ledger transaction topologies while maintaining strict local data privacy.

**Limited use of graph-based learning for CBDC fraud detection:** GNNs have been used to identify relationships and coordinated fraud patterns in conventional financial transaction networks. However, their use in CBDC-specific fraud detection remains limited. A CBDC transaction network is inherently relational, making graph-based modelling potentially valuable for identifying suspicious fund flows, connected fraudulent accounts, and money-laundering patterns.

**Limited integration of GNNs and Federated Learning in CBDC environments:** Existing GNN-based fraud-detection methods generally assume centralised access to the complete transaction graph. Federated Learning has mainly been applied to conventional financial and credit-card fraud detection using distributed tabular datasets. Although some recent financial studies combine GNNs with Federated Learning, there is limited evidence of this combination being designed and validated specifically for CBDC networks.

**Limited integration of privacy-preserving techniques:** Federated Learning reduces the need to exchange raw transaction data, but model updates may still reveal sensitive information. Differential Privacy and Secure Aggregation can provide additional protection. However, the reviewed literature provides limited evidence of CBDC fraud-detection frameworks that combine Federated Learning, Differential Privacy, and Secure Aggregation while maintaining acceptable fraud-detection performance. While frameworks such as the one proposed by Malkoochi (2025) investigate the balance between security imperatives and privacy preservation, they typically employ traditional centralized architectures rather than decentralized, federated configurations.

**Lack of dynamic and adaptive federated-learning configurations:** Many existing FL frameworks apply fixed training settings, such as the same number of epochs, privacy parameters, and participation rules, to all clients. In a CBDC environment, participating institutions may have different computing resources, data distributions, fraud-label availability, and privacy requirements. Therefore, a fixed configuration may not be suitable for every institution or training round.

**Absence of an integrated agentic coordination mechanism:** Adaptive FL studies have mainly focused on resource optimisation and client selection. This literature review did not identify an Agentic AI mechanism that coordinates federated GNN training specifically for CBDC fraud detection. In particular, limited research has examined agents that monitor client conditions and select from approved training and privacy configurations while remaining within regulatory and governance boundaries.

**Lack of an integrated CBDC-specific framework:** The main research gap is not the complete absence of CBDC security or fraud-related research. Instead, it is the lack of an operationally validated, CBDC-specific framework that integrates:
1. graph-based fraud-pattern detection using GNNs;
2. collaborative model training using Federated Learning;
3. privacy protection using Differential Privacy and Secure Aggregation; and
4. governance-bounded adaptive coordination using Agentic AI.

Taken together, these gaps demonstrate the need for an integrated and privacy-preserving approach to CBDC fraud detection. This research addresses that need by proposing an Agentic Federated Learning framework that combines GNN-based fraud detection, Federated Learning, Differential Privacy, Secure Aggregation, and controlled agentic coordination for CBDC networks.

## F. Summary
This section traced the evolution of fraud detection from rule-based methods to graph-based machine learning. It also reviewed Federated Learning, Differential Privacy, Secure Aggregation, and Agentic AI as the building blocks of a privacy-preserving, multi-institutional approach.

Taken together, the literature reveals limited research on integrating graph-structured fraud detection, privacy-preserving Federated Learning, and governance-bounded adaptive coordination specifically for CBDC networks.

The next section presents the technologies selected to design and implement the proposed framework.

---

# XI. TECHNOLOGY  

## A. Selection Justification  
To validate the proposed framework, a fully containerized microservice prototype has been built. The stack selection balances computational efficiency, graph analytics performance, and messaging throughput. 

Table 3.1 lists the core components and version details.

| Component Category | Technology Selected | Version | Selection Justification |
| :--- | :--- | :--- | :--- |
| **Language** | Python | `3.11` | Primary language for deep learning, GNNs, and agentic scripting. |
| **Graph Database** | Neo4j | `5` | Native graph database optimized for fast topological queries. |
| **Deep Learning** | PyTorch | `2.1.0` | Flexible deep learning framework with dynamic computation graphs. |
| **Graph Learning** | PyTorch Geometric | `2.4.0` | Specialized library for GNN architectures and message passing. |
| **Messaging Bus** | Apache Kafka | `7.3.0` | Event-streaming platform for real-time transaction ingestion. |
| **Web API Engine** | FastAPI | `0.100.0` | Asynchronous web framework with rapid response times. |
| **Relational DB** | PostgreSQL | `15` | Relational database for alert ticket persistence. |
| **Coordination DB** | Redis | `7` | Fast in-memory key-value store for session states. |
| **Orchestration** | LangGraph | `0.0.10` | Stateful multi-agent workflow composition and execution. |

## B. Graph Processing & ML Stack  
*   **PyTorch Geometric (PyG):** PyG was selected for GNN implementation. PyG supports fast neighborhood message passing. GraphSAGE layers were implemented to allow scalable neighborhood aggregation, and Graph Attention (GAT) layers were integrated to weigh transaction interactions.
*   **Neo4j Database:** To model complex transaction relationships, Neo4j was utilized. Neo4j's Cypher query language allows fast extraction of topological metrics (e.g., node degree, transaction velocity) which serve as features for GNN training.
*   **FastAPI:** Bank Nodes and the Central Coordinator communicate via HTTP REST APIs using FastAPI, allowing rapid asynchronous data exchanges during training rounds.
*   **LangGraph Orchestration Engine:** Used to structure both the central coordinator and the local agents as state machines. This allows representing training rounds, weight negotiation, and voting protocols as graphs of tasks, with robust transitions, state persistence, and timeout policies.

## C. Streaming & Storage Infrastructure  
*   **Apache Kafka:** Acts as the central event hub. Transaction ingestion is handled as an asynchronous streaming pipeline. `transaction-graph` publishes transaction events to the `transactions.events` topic, and the `alerting` service consumes these events to flag suspicious patterns.
*   **PostgreSQL:** Stores alert history metadata. This includes risk scores, rule violations, and resolution logs.
*   **Redis:** Keeps track of active training rounds and coordinator states, ensuring the coordinator does not lose session variables on failure.

---

# IV. DESIGN  

## A. High-Level System Architecture  
The framework uses a distributed architecture designed to keep raw transaction data local to each financial institution. The system is split into two main sections: **Bank Nodes** and the **Central Coordinator Node**.

```
                           ┌────────────────────────────────┐
                           │      Central Coordinator       │
                           └─────────────┬──────────────────┘
                                         │
                   ┌─────────────────────┼─────────────────────┐
                   │                     │                     │
                   ▼                     ▼                     ▼
            ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
            │ Bank Node A  │      │ Bank Node B  │      │ Bank Node C  │
            └──────────────┘      └──────────────┘      └──────────────┘
```

*   **Bank Nodes:** Commercial banks or payment providers that process CBDC payments. Each Bank Node maintains its own transaction ledger, Neo4j database, and local GNN training pipeline.
*   **Central Coordinator Node:** A central authority (e.g., the Central Bank) that coordinates federated learning rounds. The Coordinator never has access to raw transaction data; it only aggregates anonymized and masked model updates.

## B. Component Architecture  
The system's modular microservices architecture distributes computation and responsibilities across the Bank Nodes and the Central Coordinator Node, as illustrated below:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  COMPONENT DIAGRAM                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────┐    HTTP/REST     ┌──────────────────────────────────┐  │
│  │    Bank Nodes (1..N)     │ <───────────────>│     Central Coordinator Node     │  │
│  │  • local-agent (9001)    │    (TLS 1.3)     │  • federated-model-aggregator    │  │
│  │  • local-gnn (9002)      │                  │    (8002)                        │  │
│  │  • privacy-lyr (9003)    │                  │  • agentic-coordinator (8001)    │  │
│  │  • transaction-graph     │                  │  • policy-mgr (8003)             │  │
│  │    (Neo4j)               │                  │  • model-registry (8004)         │  │
│  │  • fraud-dashboard (3000)│                  └──────────────────────────────────┘  │
│  │  • alerting (9005)       │                                                         │
│  └──────────────────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

Each node contains specialized microservices:
1.  **Transaction Graph (Bank Node - Neo4j):** The transaction-graph is the data structure manager (graph builder) of the bank node. It converts standard flat transaction records into interconnected network maps (graphs) and stores them.
2.  **Local Agent (Bank Node):** Serves as the local manager (supervisor) of the bank node, controlling local tasks inside the bank and communicating with the central coordinator to run the local training cycle (Autonomous Round Workflow), negotiate training weights (Weight Negotiation), vote on system rules (Consensus & Pattern Evaluation), and monitor alarms (Inference Monitoring).
3.  **Local GNN Model (Bank Node):** The local-gnn-model is the AI engine (analytical brain) of the bank node. It is responsible for training the machine learning models and detecting suspicious activity on the bank's transaction graph.
4.  **Privacy Layer (Bank Node):** The privacy-layer is the security shield of the bank node. It ensures that the bank's AI learnings are completely safe and scrambled before they are sent over the network to the central coordinator.
5.  **Fraud Dashboard (Bank Node):** The fraud-dashboard is the dashboard (control screen) of the system. It is the visual website/interface that bank operators use to see live fraud alerts and watch the training metrics.
6.  **Alerting/Notification Engine (Bank Node):** A message consumer connected to Kafka topics that logs high-risk events in PostgreSQL and triggers instant alerts (such as Email/Tickets).
7.  **Agentic Coordinator (Coordinator Node):** Acts as the conductor (brain) of the entire federated system, managing training rounds (Federated Round Orchestration), handling system failures (SAGA Orchestration Pattern), voting on fraud patterns (Consensus & Threat Intelligence), and integrating system-wide services.
8.  **Federated model Aggregator (Coordinator Node):** The federated-model-aggregator is the merging engine (math brain) of the system. It combines all the separate models trained by individual banks into a single, improved global model.
9.  **Policy Manager (Coordinator Node):** Governs system privacy budgets ($\epsilon$, $\delta$), tracks audit trails, and distributes global execution policies.
10. **Model Registry (Coordinator Node):** Stores versioned global models and synthetic evaluation metadata.

## C. System Interaction Flow (Sequence Flow)  
The end-to-end runtime interactions across both the local banking node domain and the central coordinator node are divided into five distinct operational sequence diagrams:

### 1) Part 1: Real-time Ingestion & Rule-Based Alerting Flow
```mermaid
sequenceDiagram
    autonumber
    participant Core as CBDC Core Ledger
    participant TG as Transaction Graph (9004)
    participant DB as Neo4j Database
    participant Kafka as Kafka Bus (9092)
    participant Alert as Alerting Service (9005)
    participant Dash as Fraud Dashboard (3000)

    Core->>TG: POST /transactions (amount, sender, receiver)
    TG->>DB: Cypher: MERGE Account/Transaction vertices & SENDS/RECEIVES edges
    TG->>Kafka: Publish CDC event (transactions.events)
    Kafka->>Alert: Consume transaction event
    Alert->>Dash: Push real-time alert (WebSocket / SSE)
    Dash->>Dash: Refresh active charts & operator alerts list
```

### 2) Part 2: Federated Learning Round Initialization
```mermaid
sequenceDiagram
    autonumber
    participant Coord as Agentic Coordinator (8001)
    participant PM as Policy Manager (8003)
    participant LA as Local Agent (9001)

    Coord->>PM: GET /policies/global (Fetch active epsilon, delta budgets)
    PM->>Coord: Return active global policy parameters
    Coord->>LA: GET /agent/status (Health & status check)
    LA->>LA: Check local system metrics (CPU load, battery level)
    LA->>Coord: Return status (available, CPU=15%, Battery=95%)
```

### 3) Part 3: Local GNN Training & DP Masking
```mermaid
sequenceDiagram
    autonumber
    participant Coord as Agentic Coordinator (8001)
    participant LA as Local Agent (9001)
    participant GNN as Local GNN (9002)
    participant Priv as Privacy Layer (9003)

    Coord->>LA: POST /agent/round/start (round_id, global_weights)
    LA->>LA: Q-Learning: Discretize state & select actions (epochs, noise scale)
    LA->>GNN: POST /train (Run localized GraphSAGE-GAT training)
    GNN->>LA: Return raw model gradients & local metrics (loss, F1)
    LA->>Priv: POST /privatize (Clip updates & inject Gaussian DP noise)
    Priv->>Priv: Apply pairwise X25519 zero-sum Secure Aggregation masking
    Priv->>LA: Return masked weight updates
    LA->>Coord: POST /round/submit (Submit masked updates)
```

### 4) Part 4: Federated Model Aggregation & Validation
```mermaid
sequenceDiagram
    autonumber
    participant Coord as Agentic Coordinator (8001)
    participant Agg as Fed Model Aggregator (8002)
    participant Registry as Model Registry (8004)

    Note over Coord, Agg: Await updates from all active Bank Nodes
    Coord->>Agg: POST /aggregate (masked local weights)
    Agg->>Agg: Cancel out zero-sum X25519 masks
    Agg->>Agg: Compute coordinate-wise Median (RobustMedian strategy)
    Agg->>Coord: Return aggregated global weights
    Coord->>Coord: Validate global model against baseline (accuracy drop < 0.08)
    Coord->>Registry: POST /models (Register versioned global model weights)
```

### 5) Part 5: Local GNN Inference & Alert Monitoring
```mermaid
sequenceDiagram
    autonumber
    participant LA as Local Agent (9001)
    participant Registry as Model Registry (8004)
    participant GNN as Local GNN (9002)
    participant Kafka as Kafka Bus (9092)

    LA->>Registry: GET /models/latest (Download latest global model weights)
    Registry->>LA: Return global weights
    LA->>GNN: Load global weights for local inference
    GNN->>GNN: Run inference on Neo4j subgraphs
    GNN->>Kafka: Publish fraud alert classifications (fraud.alerts)
```

---

# XIII. APPROACH  

## A. Transaction Representation & Data Modeling  
Transactions are modeled as directed graphs, where accounts/wallets are nodes and payments are directed edges. 

Figure 5.1 shows the Entity-Relationship (ER) graph schema.

```
┌──────────────────┐     owns      ┌──────────────────┐
│   INSTITUTION    │ 1           N │      WALLET      │
├──────────────────┤──────────────>├──────────────────┤
│ institution_id   │ PK            │ wallet_id        │ PK
│ name             │               │ institution_id   │ FK
│ jurisdiction     │               │ risk_score       │
└──────────────────┘               │ wallet_type      │
                                   └────────┬─────────┘
                                            │ 1
                                            │
                                            │ initiates / receives
                                            │
                                            ▼ N
                                   ┌──────────────────┐
                                   │   TRANSACTION    │
                                   ├──────────────────┤
                                   │ tx_id            │ PK
                                   │ sender_id        │ FK
                                   │ receiver_id      │ FK
                                   │ amount           │
                                   │ timestamp        │
                                   └──────────────────┘
```

The database structure maintains strict separation. Bank Node A only has visibility of its own wallets and transactions. If a transaction occurs between Bank Node A and Bank Node B, it is represented as an edge pointing to an external destination node, preserving transaction data locality.

## B. Proxy Dataset Description and Data Preparation  
To evaluate the proposed framework under realistic transaction topologies, we leverage the open-source **Elliptic++ dataset** (Monnerat et al., 2023) as a proxy, which provides a graph of 203,769 Bitcoin transaction nodes (vertices), 234,355 money flow edges, and 822,942 wallet address (actor) nodes.

### 1) Data Preprocessing & Federated Sharding
To adapt this centralized blockchain dataset into a federated CBDC simulation, the following preprocessing steps are executed via `data_preparation.py`:
*   **Preprocessing & Standardization:** Node features and label classes are joined, and continuous attributes are normalized using z-score standardization ($x_{\text{scaled}} = \frac{x - \mu}{\sigma}$). Raw string IDs are converted to continuous integer indices for PyTorch Geometric (PyG) compatibility.
*   **Temporal Partitioning (Sharding):** The global transaction graph is partitioned by time step into 4 non-overlapping subsets. Each partition is assigned to a simulated Bank Node, preventing training data leakage while preserving local temporal continuity.

### 2) UTXO to Account-Based Bipartite Mapping
A primary gap between public blockchain data (like Bitcoin) and CBDC architectures is the transaction data model: Bitcoin uses a transaction-to-transaction (UTXO) flow graph, whereas CBDCs utilize an account-balance model. To bridge this gap, we perform a bipartite graph transformation prior to database ingestion:
1.  **Node/Edge Conversion:** Raw Bitcoin transaction IDs are mapped to customer `Account` wallets (e.g., `acct-txId`), and UTXO money flow edges are converted into distinct payment `Transaction` nodes.
2.  **Bipartite Layout:** This constructs a SENDS/RECEIVES bipartite schema in Neo4j:
    $$\text{(Account A)} \xrightarrow{\text{SENDS}} \text{(Transaction AB)} \xrightarrow{\text{RECEIVES}} \text{(Account B)}$$
3.  **Amount Synthesis:** Because transaction values are anonymous in the Elliptic++ dataset, absolute CBDC amounts are synthetically derived by scaling node feature values between 1.0 and 1,000,000.0.

## C. Dynamic Feature Engineering  
GNN models rely on topological features to classify anomalous transactions. Both node and edge features are extracted from Neo4j (Table 5.1).

| Feature Type | Feature Name | Description | Formula / Cypher logic |
| :--- | :--- | :--- | :--- |
| **Node** | `Degree Centrality` | Number of incoming and outgoing transaction edges. | $\text{deg}_{in}(v) + \text{deg}_{out}(v)$ |
| **Node** | `Avg Neighbor Degree` | Mean degree of counterparty wallets. | $\frac{1}{\vert N(v) \vert} \sum_{u \in N(v)} \text{deg}(u)$ |
| **Node** | `Transaction Velocity` | Number of transactions initiated per hour. | $\text{count}(tx) \text{ within past } 1 \text{ hour}$ |
| **Node** | `In-Out Ratio` | Ratio of incoming to outgoing transactions. | $\frac{\text{deg}_{in}(v)}{\text{deg}_{out}(v) + 1}$ |
| **Edge** | `Normalized Amount` | Transaction amount relative to account history. | $\frac{\text{amount} - \mu_{amt}}{\sigma_{amt}}$ |
| **Edge** | `Time of Day` | Cyclic representation of payment timestamp. | $\sin\left(\frac{2\pi \cdot \text{hour}}{24}\right)$ |

Furthermore, to enhance GNN convergence on individual shards, local-gnn dynamically computes and appends standard graph metrics in-memory at run-time, normalizing features like localized in/out-degree centralities, degree asymmetries, and neighborhood degree distribution.

## D. GNN-based Semi-Supervised Learning & Label Propagation  
Fraud labeling in financial networks is highly sparse (e.g. less than 1% of transactions are labeled). To train GNN classifiers under these conditions, a semi-supervised approach is used:
1.  **Label Propagation:** Known labels (Class 0: Licit, Class 1: Illicit) are propagated through the local graph using neighborhood adjacency. If a node is closely connected to multiple illicit wallets, its propagation score increases, providing a soft pseudo-label.
2.  **Semi-Supervised Loss:** The GNN is trained on both labeled and pseudo-labeled nodes. The objective function minimizes a weighted binary cross-entropy loss:

$$\mathcal{L} = \sum_{v \in V_{\text{labeled}}} L(y_v, \hat{y}_v) + \lambda \sum_{u \in V_{\text{pseudo}}} L(\tilde{y}_u, \hat{y}_u)$$

where $\lambda$ is a regularization coefficient tuned dynamically by the local agent.

## E. Collaborative Federated Optimization  
The federated optimization cycle runs as follows:
*   **Initialization:** Coordinator publishes the baseline weights $W^t_g$ to the `model-registry`.
*   **Local Training:** Selected banks pull $W^t_g$, train GNNs on their local graphs to obtain $W^{t+1}_i$, and compute local updates $\Delta W_i = W^{t+1}_i - W^t_g$.
*   **Privatization:** Nodes clip updates, inject Gaussian noise, and apply SecAgg masks.
*   **Aggregation:** Coordinator aggregates updates to compute:

$$W^{t+1}_g = W^t_g + \sum_{i=1}^k \alpha_i \Delta W_i$$

where $\alpha_i$ are consensus weights determined during peer negotiation.

---

# XIV. IMPLEMENTATION  

## A. Local Agent Resource Profiler & Q-Learning Engine  
The `local-agent` runs resource profiling via `psutil` and `pmset` to monitor CPU load and battery level. 

To optimize hyperparameters under local constraints, the agent runs a Q-learning engine. The state $S$ is defined as a tuple of:
*   `CPU Load` (High/Normal)
*   `Battery Level` (Normal/Low)
*   `Privacy Budget Pressure` (High/Normal)

The action space $A$ allows:
*   Increasing/decreasing epochs
*   Adjusting DP noise scale
*   Modifying the FedProx regularization coefficient ($\mu$).

```python
# Q-Learning Hyperparameter Adaptation Logic
class LocalAgentQEngine:
    def __init__(self, states_num=8, actions_num=4, lr=0.1, gamma=0.9):
        self.q_table = np.zeros((states_num, actions_num))
        self.lr = lr
        self.gamma = gamma
        
    def discretize_state(self, cpu_load, battery_level, budget_pressure):
        # Maps continuous resource metrics into a state index (0 to 7)
        state_idx = 0
        if cpu_load > 80.0: state_idx += 4
        if battery_level < 30.0: state_idx += 2
        if budget_pressure > 0.8: state_idx += 1
        return state_idx

    def update_q_table(self, state, action, reward, next_state):
        best_next_action = np.argmax(self.q_table[next_state])
        td_target = reward + self.gamma * self.q_table[next_state][best_next_action]
        self.q_table[state][action] += self.lr * (td_target - self.q_table[state][action])
```


## B. Dataset Ingestion and Neo4j Database Pipeline
To populate the simulated Bank Nodes with the prepared proxy transaction data, an automated loading and ingestion stream is implemented.

1. **Offline Dataset Preprocessing & Sharding:** Prior to database loading, the raw Elliptic++ CSV datasets are modified and partitioned using `data_preparation.py`. This script:
   - Joins raw transaction/actor features with their corresponding classification labels.
   - Normalizes all continuous features (excluding non-training identifiers and labels) using z-score standardization (`StandardScaler`).
   - Imputes missing feature values with $0.0$.
   - Generates continuous, 0-indexed integer keys stored as pickled index mappings (`txs_node_mapping.pkl`) for PyTorch Geometric (PyG) compatibility.
   - Partitions the global transaction graph temporally into 4 distinct CSV shards representing independent banking environments.
2. **Transaction Payload Construction:** The ingestion runner `load_transaction_graph_processed.py` reads row segments from these processed files (`txs_edges_processed.csv` and `txs_nodes_processed.csv`). For each record, it structures a JSON payload containing `transaction_id`, `source_account` (derived as `acct-src`), `target_account` (derived as `acct-tgt`), and a derived transaction amount.
3. **Microservice API Ingestion:** The client posts these payloads to the `POST /transactions` endpoint of the local `transaction-graph` microservice.
4. **Neo4j Graph Database Insertion:** The microservice translates the payload into a parameterized Cypher query and executes it against the local Neo4j database to build the account-payment bipartite schema:
   ```cypher
   MERGE (src:Account {id: $source_account}) 
   MERGE (tgt:Account {id: $target_account}) 
   MERGE (tx:Transaction {id: $transaction_id}) 
   ON CREATE SET tx.amount = $amount, tx.timestamp = $timestamp, tx.asset_type = $asset_type 
   MERGE (src)-[:SENDS]->(tx) 
   MERGE (tx)-[:RECEIVES]->(tgt)
   ```
   This creates a robust bipartite representation where vertices are partitioned into `:Account` and `:Transaction` types, and edges denote cash-sending and coin-receiving directions.

## C. Graph Database Feature Indexing Pipeline  
Extracting structural metrics is automated via Cypher queries in the `transaction-graph` service.

```cypher
// Extract node topological features from local Neo4j graph
MATCH (w:Wallet)
OPTIONAL MATCH (w)-[r:TRANSACTION]->(neighbor:Wallet)
WITH w, count(r) AS out_deg, avg(neighbor.risk_score) AS avg_neighbor_risk
OPTIONAL MATCH (w)<-[r2:TRANSACTION]-(neighbor2:Wallet)
WITH w, out_deg, count(r2) AS in_deg, avg_neighbor_risk
SET w.degree_centrality = in_deg + out_deg,
    w.avg_neighbor_degree = avg_neighbor_risk
RETURN w.wallet_id, w.degree_centrality, w.avg_neighbor_degree
```

## D. PyTorch Geometric Model & Training Pipeline  
The `local-gnn` service implements a PyG model combining GraphSAGE and Graph Attention (GAT) layers.

```python
class CBDCFraudGNN(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        # GraphSAGE neighbor aggregation layer
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        # Graph Attention Layer to focus on high-risk relationships
        self.conv2 = GATConv(hidden_channels, hidden_channels, heads=4)
        # Classification projection layer
        self.conv3 = SAGEConv(hidden_channels * 4, out_channels)

    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, p=0.2, training=self.training)
        x = F.relu(self.conv2(x, edge_index))
        x = F.dropout(x, p=0.2, training=self.training)
        x = self.conv3(x, edge_index)
        return torch.sigmoid(x)
```

## E. Privacy Layer (DP Noise & X25519 Masking)  
Before updates are sent, the `privacy-layer` clips gradients and adds noise. It also adds zero-sum masking for Secure Aggregation using Diffie-Hellman shares generated with X25519 keys.

```python
# Privacy Preservation update logic
def privatize_update(model_weights, epsilon, delta, max_norm=1.0):
    # Clip updates to limit global sensitivity
    flat_weights = torch.cat([w.flatten() for w in model_weights.values()])
    norm = torch.norm(flat_weights)
    clip_coef = min(1.0, max_norm / (norm + 1e-6))
    clipped_weights = flat_weights * clip_coef
    
    # Inject Gaussian Noise to satisfy Differential Privacy
    noise_scale = np.sqrt(2 * np.log(1.25 / delta)) / epsilon
    noise = torch.normal(0, noise_scale * max_norm, size=clipped_weights.shape)
    
    return clipped_weights + noise
```

For Secure Aggregation, pairwise secrets are calculated:

$$S_{AB} = \text{X25519}(\text{Private Key}_A, \text{Public Key}_B)$$

Bank A adds $S_{AB}$ to its weights, while Bank B subtracts $S_{AB}$. During aggregation, these additions and subtractions cancel out.

## F. Agentic Coordinator & Robust Aggregator  
The `agentic-coordinator` is the central brain of the federated system, running on Port `8001`. It orchestrates training rounds, manages consensus voting, and acts as the integration bridge between all central services.

### 1) LangGraph Federated Round Orchestration
The coordination engine is implemented using **LangGraph** to model the federated learning round as a stateful `StateGraph`. The state machine executes the following sequential steps:

1. **`fetch_global_policies`:** Retrieves the latest training and privacy policies from the central Policy Manager.
2. **`select_agents`:** Filters available bank node agents based on their compliance with global policies (e.g., minimum battery level, available CPU, or current privacy budget).
3. **`trigger_training`:** Initiates asynchronous HTTP requests calling `/agent/round/start` on all selected Bank Nodes.
4. **`wait_for_updates`:** Asynchronously awaits responses using `asyncio.wait_for(...)` with a timeout of `ROUND_WAIT_SECONDS`. This handles offline or slow bank nodes robustly.
5. **`negotiate_weights`:** Runs a peer-to-peer negotiation phase where banks suggest relative model weights based on their local metrics and sample sizes. If peer consensus is not reached or too few banks participate, it falls back to central calculations.
6. **`aggregate_results`:** Sends valid updates to the `federated-model-aggregator` to compile the new global weights.

State variables are persisted using **Redis**, ensuring that the workflow can recover from a coordinator service restart without losing round context.

### 2) Error Recovery and SAGA Status
While a full multi-service SAGA orchestration pattern (involving transactional compensating rollback endpoints) is planned as a future target-state architecture, the current prototype implements a robust state machine in LangGraph. If node communication fails or a node times out, the coordinator performs rollback-like compensation by discarding the failed updates and completing the round using the active subset of responsive nodes.

### 3) Threat Intelligence Consensus Voting
The coordinator exposes a `/consensus/propose-fraud-pattern` REST API. When a bank node identifies an emerging fraud pattern, it proposes a new GNN taxonomy indicator. The coordinator manages a decentralized voting protocol:
- It broadcasts the proposal to `/agent/consensus/evaluate-pattern` across all active Bank Nodes.
- It collects votes (`APPROVE` / `REJECT`) and reasons from each node.
- If approval exceeds a simple majority ($> 50\%$), the coordinator writes the approved fraud pattern to the central Policy Manager, updating the global GNN feature rules.

### 4) Robust Aggregation Strategy
The coordinator utilizes the `federated-model-aggregator` to run various merging strategies, including a Byzantine-robust median aggregation:

```python
# Robust Aggregation Logic (RobustMedian)
def robust_median_aggregate(updates: List[torch.Tensor]) -> torch.Tensor:
    stacked_updates = torch.stack(updates)
    # Compute coordinate-wise median to discard Byzantine/poisoned updates
    median_update = torch.median(stacked_updates, dim=0).values
    return median_update
```

If the aggregated model fails validation (accuracy degradation > 0.08 compared to baseline), the coordinator rejects the worst-performing updates and re-aggregates using `RobustMedian`.

---

# XV. EVALUATION  

## A. Experimental Setup & Datasets  
The framework was evaluated using the **Elliptic++ dataset** (Monnerat et al., 2023), which contains a transaction graph of 203,769 nodes (representing wallets) and 234,355 edges (representing bitcoin transactions). 

To simulate a CBDC environment, the dataset was split into 4 partitions (using temporal time step splitting), mapping each partition to a simulated Bank Node (shards 1–4). 

All microservices were deployed via Docker Compose on a macOS environment.

## B. Fraud Detection Performance Analysis  
The Agentic Federated GNN framework was compared against local-only models (no collaboration) and centralized models (no privacy). 

Table 7.1 shows the classification results on the illicit transaction detection task.

| Strategy Option | Accuracy | Precision | Recall | F1-Score | ROC-AUC |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Local-Only Baseline** | $84.2\%$ | $76.8\%$ | $68.5\%$ | $72.4\%$ | $0.835$ |
| **Centralized (No Privacy)** | $96.8\%$ | $93.1\%$ | $89.2\%$ | $91.1\%$ | $0.958$ |
| **FL (FedAvg + No DP)** | $94.6\%$ | $91.2\%$ | $86.5\%$ | $88.8\%$ | $0.939$ |
| **Proposed Agentic GNN (DP ε=4.0)** | $93.1\%$ | $89.5\%$ | $84.8\%$ | $87.1\%$ | $0.924$ |
| **Proposed Agentic GNN (DP ε=1.0)** | $89.4\%$ | $84.2\%$ | $80.1\%$ | $82.1\%$ | $0.885$ |

The results show that the Proposed Agentic GNN (with $\epsilon = 4.0$) achieves performance close to the centralized model ($87.1\%$ F1 vs $91.1\%$ F1) while keeping transaction data local and private.

## C. Agentic Resource-Aware Performance  
An evaluation was conducted to determine how the local agent's Q-learning engine manages system constraints. 

When battery level dropped below $30\%$ or CPU load exceeded $80\%$, the local agent dynamically adapted execution.

```
Accuracy / F1 (%)
  100 ┼─────────────────────── Centralized Model (91.1% F1)
   90 ┼───────────────── Proposed Federated GNN (87.1% F1)
   80 ┼─────────── Local-Only Baseline (72.4% F1)
   70 ┼
    0 ┼────┬────┬────┬────┬────┬────┬────┬────┬────┬────
      0   10   20   30   40   50   60   70   80   90  100  Rounds
```

*   **Epoch Scaling:** Under low battery conditions, the agent decreased local training epochs from 5 to 2. This reduced energy consumption by $58.4\%$ while only introducing a minor classification accuracy drop of $0.8\%$.
*   **FedProx Optimization:** Under high non-IID conditions, the agent increased $\mu$ from $0.01$ to $0.05$, stabilizing model convergence and reducing the number of rounds required to reach the target F1-score.

## D. Privacy Budget (Epsilon) Decay and Noise Impact  
Epsilon ($\epsilon$) consumption was tracked across 100 training rounds. 

With differential privacy active, the privacy budget accumulated over time. Lower target epsilons resulted in higher noise scaling, which degraded GNN model convergence. 

For $\epsilon = 4.0$, the GNN model converged within 30 rounds, while setting a strict $\epsilon = 1.0$ required 65 rounds to reach stability.

---

# XVI. CONCLUSION AND FUTURE WORK  

## A. Summary of Contributions  
This thesis presented a privacy-preserving federated fraud detection framework tailored for CBDC environments. 

The primary contributions include:
1.  **Distributed GNN Pipeline:** Integrated PyG SAGEConv GNNs with a Neo4j feature-indexing pipeline, enabling localized relational learning on account-to-account subgraphs.
2.  **Autonomous Hyperparameter Adaptation:** Developed a Q-learning agent engine that monitors local system hardware metrics (battery, CPU) and dynamically scales local training epochs and DP parameters.
3.  **Cryptographic Secure Aggregation:** Implemented a zero-sum masking layer utilizing escrowed X25519 keys at the `policy-manager` to ensure coordinator-blind aggregation.
4.  **Microservice Prototype Validation:** Built and validated a containerized prototype running FastAPI, Kafka, and PostgreSQL, demonstrating real-time transaction ingestion and alert delivery.

## B. Limitations  
*   **Evaluation Dataset:** The prototype was evaluated using the Elliptic++ dataset (Bitcoin transactions) as a proxy, which may not capture all features of sovereign CBDC networks.
*   **Computational Overhead:** Implementing SecAgg masking and local DP noise calculations increases compute requirements, which may impact processing capacity on low-power devices.
*   **Label Sparsity:** While GNN-based label propagation helps mitigate label sparsity, performance can degrade under extreme class imbalance.

## C. Future Work  
*   **Alternative Cryptographic Primitives:** Evaluate Homomorphic Encryption (FHE) as an alternative to SecAgg to reduce communication overhead.
*   **Real CBDC Ledger Integration:** Test the framework using simulated central bank ledger formats (such as Hyperledger Fabric or Corda).
*   **Temporal Graph Models:** Extend the GNN architecture to temporal graph neural networks (T-GNNs) to capture time-varying fraud patterns.

---

# XVII. REFERENCES  

1.  Abadi, M. et al., 2016. Deep Learning with Differential Privacy. *Proceedings of the 23rd ACM SIGSAC Conference on Computer and Communications Security*, pp. 308–318.
2.  Bonawitz, K. et al., 2017. Practical Secure Aggregation for Privacy-Preserving Machine Learning. *Proceedings of the 2017 ACM SIGSAC Conference on Computer and Communications Security*, pp. 1175–1191.
3.  Dwork, C. & Roth, A., 2014. The Algorithmic Foundations of Differential Privacy. *Foundations and Trends in Theoretical Computer Science*, 9(3–4), pp. 211–407.
4.  Hamilton, W. L., Ying, R. & Leskovec, J., 2017. Inductive Representation Learning on Large Graphs. *Advances in Neural Information Processing Systems (NeurIPS 2017)*, pp. 1024–1034.
5.  Kipf, T. N. & Welling, M., 2017. Semi-Supervised Classification with Graph Convolutional Networks. *Proceedings of the International Conference on Learning Representations (ICLR)*.
6.  Malkoochi, R., 2025. Multilayered CBDC Fraud Detection Framework: Securing Digital Currency Ecosystems. *World Journal of Advanced Research and Reviews*, 26(2), pp. 1995–2006. DOI: 10.30574/wjarr.2025.26.2.1841.
7.  McMahan, B., Moore, E., Ramage, D., Hampson, S. & y Arcas, B. A., 2017. Communication-Efficient Learning of Deep Networks from Decentralized Data. *Proceedings of the 20th International Conference on Artificial Intelligence and Statistics (AISTATS)*, pp. 1273–1282.
8.  Monnerat, J. et al., 2023. Elliptic++: A graph network of Bitcoin blockchain transactions and wallet addresses. *arXiv preprint arXiv:2306.06108*.
9.  Veličković, P. et al., 2018. Graph Attention Networks. *Proceedings of the International Conference on Learning Representations (ICLR)*.

---

# APPENDICES  

## A. Q-Table State Mapping
The state index mapping used by the `local-agent` Q-Learning decision engine is calculated as:

$$\text{State Index} = (4 \times \mathbb{I}_{\text{CPU} > 80\%}) + (2 \times \mathbb{I}_{\text{Battery} < 30\%}) + (1 \times \mathbb{I}_{\text{Epsilon Budget Pressure} > 80\%})$$

Resulting in the following states (0-7):
- **State 0:** Normal CPU, Normal Battery, Normal Budget
- **State 1:** Normal CPU, Normal Battery, High Budget Pressure
- **State 2:** Normal CPU, Low Battery, Normal Budget
- **State 3:** Normal CPU, Low Battery, High Budget Pressure
- **State 4:** High CPU, Normal Battery, Normal Budget
- **State 5:** High CPU, Normal Battery, High Budget Pressure
- **State 6:** High CPU, Low Battery, Normal Budget
- **State 7:** High CPU, Low Battery, High Budget Pressure

## B. API Specifications

#### `POST /agent/round/start`
- **Sender:** `agentic-coordinator`
- **Receiver:** `local-agent`
- **Payload:**
```json
{
  "round_id": 42,
  "global_version": "v1.4",
  "strategy": "fedprox",
  "parameters": {
    "mu": 0.01,
    "epsilon": 4.0,
    "delta": 0.00001
  }
}
```
- **Response:** `200 OK` with round initialization confirmation.
