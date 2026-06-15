---
title: "MSc Data Science Project Proposal"
author: "WAD Dusman Nalin Dayawansha"
student_id: "K2557706"
supervisor: "Dr. Madhawa Ranawake"
date: "30.01.2026"
university: "Kingston University"
---

# MSc. Data Science  
## Project Proposal

**Name:** WAD Dusman Nalin Dayawansha  
**ID Number:** K2557706  

## Project Title  
**An Agentic Federated Learning Framework for Privacy Preserving Fraud Detection in Central Bank Digital Currency (CBDC) Networks**

**Supervisor:** Dr. Madhawa Ranawake  
**Date:** 30.01.2026  

**Kingston University**

---

# Table of Contents

1. [List of Figures](#list-of-figures)  
2. [Glossary of Terms](#glossary-of-terms)  
3. [Abstract](#abstract)  
4. [Introduction & Background](#introduction--background)  
   - [Introduction](#introduction)  
   - [Background and Motivation](#background-and-motivation)  
   - [Context](#context)  
   - [Problem Statement](#problem-statement)  
   - [Proposed Solution](#proposed-solution)  
5. [Aim & Research Objectives](#aim--research-objectives)  
   - [Aim](#aim)  
   - [Objectives](#objectives)  
   - [SMART Objectives](#smart-objectives)  
6. [Literature Review](#literature-review)  
   - [Overview](#overview)  
   - [Gap in Literature](#gap-in-literature)  
7. [Design](#design)  
   - [System Architecture Overview](#system-architecture-overview)  
   - [System Architecture Diagram](#system-architecture-diagram)  
   - [Sequence Diagram](#sequence-diagram)  
   - [Central Coordinator Node (No Raw Data Access)](#central-coordinator-node-no-raw-data-access)  
   - [Bank Node Architecture](#bank-node-architecture)  
   - [Deployment and Scalability Considerations](#deployment-and-scalability-considerations)  
8. [Technology](#technology)  
   - [Required Technologies](#required-technologies)  
   - [Alternatives Considered](#alternatives-considered)  
   - [Software Tools](#software-tools)  
9. [Test Data and Data Preparation](#test-data-and-data-preparation)  
   - [Test Data Source](#test-data-source)  
   - [CBDC-like Simulation Assumption](#cbdc-like-simulation-assumption)  
   - [Data Preparation](#data-preparation)  
10. [Research Methodology](#research-methodology)  
    - [Research Design](#research-design)  
    - [Data Collection](#data-collection)  
    - [Data Preparation](#data-preparation-1)  
    - [AI Model Development](#ai-model-development)  
    - [Model Evaluation](#model-evaluation)  
11. [Ethical Considerations](#ethical-considerations)  
    - [Work Plan](#work-plan)  
    - [Time Line](#time-line)  
12. [Deliverables](#deliverables)  
13. [Expected Outcomes and Limitations](#expected-outcomes-and-limitations)  
    - [Expected Outcomes](#expected-outcomes)  
    - [Limitations](#limitations)  
    - [Future Work](#future-work)  
14. [References](#references)  

---

# List of Figures

1. Architecture  
2. Sequence  

---

# Glossary of Terms

- **AI** – Artificial Intelligence  
- **CBDC** – Central Bank Digital Currency  
- **FL** – Federated Learning  
- **GNN** – Graph Neural Network  
- **ML** – Machine Learning  
- **DP** – Differential Privacy  
- **GDPR** – General Data Protection Regulation  
- **PSD2** – Payment Services Directive 2  
- **Non-IID** – Non-Independent and Identically Distributed Data  
- **FedAvg** – Federated Averaging Algorithm  

---

# Abstract

The rapid evolution Central Bank Digital Currencies (CBDCs) are rapidly emerging as a regulated alternative to cryptocurrencies, offering programmable, traceable, and sovereign digital money. However, the introduction of CBDCs also increases exposure to sophisticated and cross-institutional fraud patterns. Traditional centralized fraud detection systems are increasingly incompatible with strict privacy regulations such as the General Data Protection Regulation (GDPR) and the Payment Services Directive 2 (PSD2), as they require access to large volumes of sensitive transaction data.

This research proposes an Agentic Federated Learning framework for privacy-preserving fraud detection in CBDC networks. The framework enables multiple financial institutions to collaboratively train fraud detection models without sharing raw transaction data. By combining Federated Learning, Graph Neural Networks (GNNs), and Agentic AI, the proposed system supports autonomous coordination, adaptive learning, and continuous fraud mitigation while maintaining regulatory compliance. The outcome of this research is a working prototype and a validated architecture demonstrating privacy-first, adaptive fraud detection suitable for CBDC ecosystems.

---

# Introduction & Background

## Introduction

The rapid digitization of financial services has fundamentally transformed how money is created, transferred, and monitored. Central Bank Digital Currencies (CBDCs) have emerged as a strategic response by governments and monetary authorities to the rise of decentralized cryptocurrencies and private digital payment systems. Unlike cryptocurrencies, CBDCs are issued and regulated by central banks, ensuring monetary stability, legal tender status, and regulatory oversight. As a result, CBDCs are increasingly viewed as a critical component of future national and cross-border payment infrastructures.

However, the introduction of CBDCs also significantly expands the digital attack surface of financial systems. The high volume, velocity, and programmability of CBDC transactions make them attractive targets for sophisticated fraud schemes, including money laundering, identity fraud, transaction manipulation, and coordinated cross-institutional attacks. Detecting such fraud in real time is a complex task that requires advanced analytical techniques capable of reasoning over large-scale transactional data.

## Background and Motivation

### 1) Motivation

Fraud detection has traditionally relied on centralized monitoring systems that collect transaction data from multiple sources into a single analytical platform. While effective in some contexts, this approach poses serious challenges in CBDC environments, where transaction data is highly sensitive and subject to strict privacy regulations. Laws such as GDPR and PSD2 explicitly limit how personal and financial data can be shared, stored, and processed, particularly across institutional and national boundaries.

The motivation for this research arises from the tension between the need for collaborative fraud detection and the obligation to preserve data privacy and institutional autonomy. Financial institutions must be able to detect fraud patterns that span multiple entities, yet they cannot legally or ethically share raw transaction data. This research is motivated by the need to design a system that resolves this conflict by enabling collective intelligence without centralized data access.

### 2) Background

Federated Learning (FL) has gained prominence as a privacy-aware machine learning paradigm that allows multiple participants to jointly train a shared model while keeping their data local. In parallel, Graph Neural Networks (GNNs) have demonstrated strong performance in fraud detection tasks by modeling relationships between entities such as accounts, wallets, and transactions. More recently, Agentic AI has emerged as a paradigm for building autonomous systems that can make decisions, adapt to changing environments, and operate with minimal human intervention.

Despite these advancements, existing research often treats these technologies in isolation. Most federated learning systems operate with static coordination logic, while many fraud detection models lack the ability to adapt autonomously to emerging fraud patterns. This research builds upon these foundations by integrating FL, GNNs, and Agentic AI into a unified, privacy-preserving framework tailored specifically for CBDC networks.

## Context

This research is conducted within the context of regulated digital finance, where compliance, auditability, and trust are paramount. The proposed framework is designed to operate in environments involving central banks, commercial banks, payment service providers, and regulatory authorities. The system assumes heterogeneous institutional participants, each operating under its own data governance policies, computational constraints, and regulatory obligations.

## Problem Statement

Existing fraud detection systems face a fundamental limitation in CBDC environments. Centralized approaches violate privacy and regulatory constraints, while isolated, institution-specific models lack the global visibility required to detect coordinated fraud. Furthermore, most existing systems are reactive and static, requiring manual intervention to adapt to new fraud tactics. There is a clear need for a system that is collaborative, privacy-preserving, and autonomous.

## Proposed Solution

This research proposes an Agentic Federated Learning framework in which each participating institution maintains a local transaction graph and trains a GNN-based fraud detection model. Privacy-safe model updates are shared through federated learning, while an agentic coordinator autonomously manages training rounds, policy enforcement, and system adaptation. By combining relational learning, privacy-preserving collaboration, and autonomous control, the proposed solution aims to deliver effective and compliant fraud detection for CBDC networks.

---

# Aim & Research Objectives

## Aim

1) To To develop an Agentic Federated Learning framework that enables privacy-preserving, adaptive, and collaborative fraud detection across Central Bank Digital Currency (CBDC) ecosystems without requiring institutions to share sensitive transaction data.

## Objectives

1) **To Develop a Federated Learning Framework for CBDC Fraud Detection.**  
To Develop a Federated Learning Framework for CBDC Fraud Detection that enables a distributed learning setup in which each institution trains a local model without sharing raw transaction data, thereby ensuring privacy and regulatory compliance.

2) **To Develop Agentic AI Capabilities**  
To develop agentic components capable of managing training rounds, monitoring model behavior, and adapting the learning workflow with minimal human intervention.

3) **To Develop a Privacy-Preserving Training Pipeline**  
To develop privacy-preserving mechanisms such as encrypted model updates, differential privacy, or secure aggregation to ensure sensitive CBDC transaction data is never exposed.

4) **To Develop a Prototype**  
To develop a working prototype demonstrating how federated learning and agentic coordination can jointly detect fraud in a privacy-preserving CBDC-like environment.

## SMART Objectives

- **Specific:** Implement a federated GNN-based fraud detection prototype.  
- **Measurable:** Evaluate performance using Precision, Recall, F1-score, and ROC-AUC.  
- **Achievable:** Use synthetic and open-source datasets for simulation.  
- **Relevant:** Address privacy and compliance challenges in CBDC systems.  
- **Time-bound:** Complete design, implementation, and evaluation within the project timeline.

---

# Literature Review

This chapter reviews existing academic and industry literature relevant to fraud detection in digital financial systems, federated learning, graph-based machine learning, and agentic AI. The purpose of this review is to establish the theoretical and technical foundations of the proposed research, identify limitations in current approaches, and clearly position the contribution of this study within the existing body of knowledge.

## Overview

### 1) Fraud Detection in Digital and CBDC-like Financial Systems

Fraud detection has long been a critical research area in financial technology, particularly with the growth of digital payments and online banking. Traditional fraud detection approaches rely on rule-based systems and supervised machine learning models trained on historical transaction data. While these methods have demonstrated effectiveness in controlled environments, they struggle to adapt to rapidly evolving fraud strategies and often require centralized access to large volumes of sensitive data.

With the emergence of CBDCs, fraud detection challenges have intensified. CBDC transactions are typically high-frequency, highly traceable, and programmable, which creates both opportunities and risks. Studies have highlighted that CBDC infrastructures could be vulnerable to coordinated fraud attacks, transaction graph manipulation, and identity-based exploits that span multiple institutions. Existing centralized detection mechanisms are ill-suited for such environments due to regulatory restrictions on data sharing and the sheer scale of transaction data involved.

### 2) Graph-Based Fraud Detection and Graph Neural Networks

Graph-based representations have become increasingly popular in fraud detection research due to their ability to capture relationships between entities such as accounts, wallets, devices, and transactions. Unlike traditional tabular models, graph-based approaches model interactions explicitly, enabling the detection of complex and indirect fraud patterns.

Graph Neural Networks (GNNs) extend this idea by applying deep learning techniques directly to graph-structured data. Prior studies demonstrate that GNNs outperform classical machine learning models in detecting fraud scenarios involving collusion, money laundering, and transaction chains. Models such as Graph Convolutional Networks (GCNs), Graph Attention Networks (GATs), and GraphSAGE have been successfully applied to financial transaction networks. However, most existing implementations assume centralized access to the full transaction graph, which is not feasible in regulated CBDC environments.

### 3) Federated Learning for Privacy-Preserving Analytics

Federated Learning (FL) has emerged as a promising solution for collaborative model training without centralized data collection. In FL, multiple participants train local models on their own data and share only model updates with a central server. This paradigm has been widely studied in healthcare, mobile computing, and recommendation systems, where data privacy is a primary concern.

Recent research has explored the use of FL for financial fraud detection, demonstrating that federated models can achieve performance comparable to centralized models under certain conditions. However, many of these studies rely on static training schedules and assume trusted coordination mechanisms. Furthermore, federated learning alone does not fully eliminate privacy risks, as model updates can still leak sensitive information through inference attacks.

### 4) Privacy-Preserving Techniques in Federated Learning

To address privacy risks in federated learning, researchers have proposed various privacy-enhancing techniques, including differential privacy, secure aggregation, and secure multi-party computation. Differential privacy provides formal mathematical guarantees by limiting the influence of individual data points on model updates through noise addition. Secure aggregation protocols ensure that the central server can only access aggregated updates rather than individual contributions.

While these techniques significantly improve privacy guarantees, they introduce trade-offs between model accuracy, communication overhead, and system complexity. Existing literature often treats privacy mechanisms as static configurations, without considering adaptive privacy management in dynamic environments such as CBDC networks.

### 5) Agentic AI and Autonomous Learning Systems

Agentic AI refers to systems composed of autonomous agents capable of sensing their environment, reasoning over observations, and taking actions to achieve specific goals. In recent years, agentic architectures have been explored in robotics, distributed systems, and adaptive control. These systems emphasize autonomy, adaptability, and minimal human intervention.

In the context of machine learning systems, agentic components have been used to manage training workflows, optimize resource allocation, and respond to changing conditions. However, the application of agentic AI to federated learning remains limited. Most existing federated learning frameworks rely on fixed orchestration logic and lack the ability to adapt training strategies based on performance, data drift, or privacy constraints.

## Gap in Literature

Despite significant progress across the individual domains of fraud detection, federated learning, graph neural networks, and privacy-preserving AI, several critical gaps remain when these approaches are considered in the context of Central Bank Digital Currency (CBDC) systems.

Existing research has explored privacy-preserving fraud detection in related digital financial environments. For example, recent studies have investigated the use of federated learning for fraud detection in digital banking systems, demonstrating that collaborative model training can improve detection performance while reducing direct data sharing  
e.g.: Federated Learning for Privacy-Preserving Fraud Detection in Digital Banking, available at: ref1.  
Similarly, other work has examined Federated Learning for Privacy-Preserving Financial Fraud Detection ref2, Privacy-Preserving Federated Learning for Financial Crime Detection ref3.

However, these studies are primarily focused on commercial digital banking or general financial analytics, rather than CBDC ecosystems. As a result, they do not fully address the unique characteristics of CBDCs, such as sovereign issuance, central-bank-level governance, strict regulatory oversight, and the need for cross-institutional coordination without centralized access to transaction data. In addition, many existing federated learning approaches rely on static coordination mechanisms, lacking autonomous or agentic capabilities to dynamically manage participant selection, training schedules, and policy constraints.

Furthermore, although Graph Neural Networks have demonstrated strong performance in fraud detection within centralized or single-institution settings, their integration into federated learning frameworks remains limited. Most existing approaches assume simplified graph structures or homogeneous data distributions, which do not reflect the heterogeneity and institutional separation inherent in real-world CBDC networks.

Consequently, there remains a clear gap in the literature for CBDC-specific fraud detection frameworks that combine graph-based modeling, privacy-preserving federated learning, and agentic coordination mechanisms capable of operating under regulatory and governance constraints. This research aims to address this gap by proposing an Agentic Federated Learning framework tailored specifically for CBDC environments.

---

# Design

This chapter presents the architectural design of the proposed Agentic Federated Learning framework. The design focuses on enabling collaborative fraud detection across CBDC institutions while strictly preserving data privacy, regulatory compliance, and institutional autonomy. The architecture is structured to clearly separate coordination, learning, aggregation, and data ownership responsibilities.

## System Architecture Overview

The system adopts a distributed federated architecture consisting of multiple Bank Nodes and a logically centralized Central Coordinator Node. Bank Nodes retain complete control over local CBDC transaction data and model training, while the Central Coordinator Node is responsible only for orchestration, governance, aggregation, and model lifecycle management. At no stage does the central node access raw transaction data or perform local model training.

Key architectural characteristics include:
- Strict data locality at Bank Nodes.  
- Centralized coordination without data access.  
- Modular and loosely coupled components.  
- Support for adaptive and autonomous operation.  

## System Architecture Diagram

1. Architecture

## Sequence Diagram

2. Sequence

## Central Coordinator Node (No Raw Data Access)

The Central Coordinator Node functions as the system’s control and governance layer. It coordinates federated learning rounds, enforces policies, aggregates model updates, and maintains global model state, without processing or accessing sensitive transaction data.

### 1) Agentic Coordinator (Meta-Agent)

The Agentic Coordinator is responsible for autonomous orchestration of the federated learning process. It manages the full lifecycle of training rounds and introduces agentic behavior into the system.

Primary responsibilities include:
- Initiating and scheduling federated training rounds  
- Selecting participating Bank Nodes for each round  
- Configuring round-level parameters (e.g., aggregation method, constraints)  
- Monitoring global performance metrics  
- Adapting coordination strategies based on system state and policy constraints  

This component enables the system to operate continuously and adaptively without manual intervention.

### 2) Policy Manager (Privacy and Governance)

The Policy Manager defines and enforces governance and privacy rules across the system. It acts as the authoritative source of constraints under which federated learning operations must execute.

Key responsibilities include:
- Defining allowable privacy budgets and differential privacy parameters  
- Enforcing participation eligibility rules  
- Specifying minimum participation thresholds per round  
- Ensuring compliance with regulatory requirements (e.g., GDPR, PSD2)  

All decisions made by the Agentic Coordinator are constrained by the policies maintained by this component.

### 3) Secure Aggregator (FedAvg / FedGNN)

The Secure Aggregator is responsible solely for combining privacy-protected model updates received from Bank Nodes.

Its responsibilities include:
- Receiving encrypted and privacy-safe updates  
- Validating round consistency  
- Aggregating updates using FedAvg or FedGNN strategies  
- Producing updated global model parameters  

The aggregator does not access raw data, interpret model semantics, or make coordination decisions.

### 4) Model Registry (Versions and Metrics)

The Model Registry manages the storage and versioning of global models and associated evaluation metadata.

Its functions include:
- Storing successive global model versions  
- Maintaining historical records of training rounds  
- Persisting global evaluation metrics  
- Providing controlled access for Bank Nodes to retrieve the latest model  

This component supports auditability, reproducibility, and experimental evaluation.

## Bank Node Architecture

Each Bank Node represents an independent financial institution operating within its own secure environment. Bank Nodes are responsible for local data management, model training, and privacy enforcement.

### 1) Local Agent

The Local Agent manages local participation in federated learning rounds and enforces both global policies and local constraints.

Key responsibilities include:
- Deciding whether to participate in a training round  
- Initiating and supervising local model training  
- Enforcing privacy constraints and local policies  
- Controlling outbound communication from the institution  

### 2) Local GNN

The Local Graph Neural Network (GNN) Model performs fraud detection learning using institution-specific transaction data.

Key characteristics include:
- Training exclusively on local transaction graphs  
- Learning relational fraud patterns  
- Producing local predictions and model updates  
- Never being shared directly outside the institution  

### 3) Privacy Layer (Differential Privacy and Encryption)

The Privacy Layer enforces privacy guarantees before any model updates leave the Bank Node.

Its functions include:
- Applying update or gradient clipping  
- Adding differential privacy noise  
- Encrypting updates for secure transmission  

This layer ensures privacy-by-design and protects against inference attacks and data leakage.

### 4) Transaction Graph

The Transaction Graph represents local CBDC transactions as a graph structure.

Key aspects include:
- Nodes representing wallets or accounts  
- Edges representing transactions  
- Support for relational fraud analysis using GNNs  

The transaction graph remains entirely local, and raw data is never exposed externally.

## Deployment and Scalability Considerations

- Each participating financial institution deploys its Bank Node services within its own secure on-premise or private cloud environment to ensure data locality and regulatory compliance.  
- A single Central Coordinator Node is deployed on a trusted cloud platform or dedicated institutional infrastructure, with no access to raw transaction data.  
- All system components are containerized using Docker to ensure portability, reproducibility, and consistent execution across environments.  
- Kubernetes (K8s) is used to orchestrate containerized services, enabling horizontal scaling, fault tolerance, and resilient service management.  
- CI/CD pipelines are implemented using GitHub Actions integrated with Jenkins to automate build, testing, and deployment workflows.  
- The deployment architecture supports scalable onboarding of new institutions without requiring changes to existing Bank Nodes.  
- The overall design enables production-ready scalability while maintaining privacy, security, and institutional autonomy.  

---

# Technology

## Required Technologies

### 1) Programming Languages
- **Python:** Primary development language for federated learning, graph-based machine learning, and agentic coordination logic.  
- **JavaScript:** Used with React.js to develop the fraud monitoring and analytics dashboard.

### 2) Machine Learning & Graph Frameworks
- **PyTorch:** Core deep learning framework for model development.  
- **PyTorch Geometric (PyG):** Used for implementing Graph Neural Network (GNN) models on transaction graphs.

### 3) Federated Learning
- **Flower / TensorFlow Federated:** Used to coordinate federated training rounds, client participation, and model aggregation.

### 4) Agentic Components
- **Custom Agent Logic:** Implements autonomous coordination at the Central Coordinator Node and decision-making at Bank Nodes.

### 5) Data Processing & Graph Construction
- **NetworkX:** Used to construct and manage transaction graphs at Bank Nodes.  
- **Pandas / NumPy:** Used for transaction data preprocessing and feature engineering.

### 6) Privacy & Security
- **Differential Privacy:** Applied to local model updates before sharing.  
- **Encryption (TLS):** Secures communication between Bank Nodes and the Central Coordinator Node.

### 7) Deployment & Infrastructure
- **Docker:** Containerization of all system components.  
- **Kubernetes (K8s):** Orchestration of containerized microservices.  
- **GitHub Actions + Jenkins:** CI/CD pipelines for automated build, test, and deployment.

### 8) Distributed transaction handling (Supporting Infrastructure)
- **Change Data Capture (CDC):**  
  CDC may be used in limited scenarios to capture transaction state changes across distributed services, supporting asynchronous and event-driven communication where required.  
- **Apache Kafka:**  
  Kafka may be used as an event streaming platform to support CDC-based message propagation and decoupled service communication in distributed environments.  
- **HTTP-based Communication:**  
  Standard HTTP/REST communication may be used for synchronous service-to-service interactions where real-time coordination is required.

## Alternatives Considered

- Centralized Machine Learning: Rejected due to privacy and regulatory constraints.  
- Non-Graph-Based Models: Rejected due to limited ability to detect relational fraud.  
- Fully Homomorphic Encryption (FHE): Deferred due to computational overhead.  
- Blockchain-Based Coordination: Deferred due to increased system complexity.

## Software Tools

- PyTorch: Deep learning framework for model development.  
- PyTorch Geometric (PyG): Graph Neural Network implementation on transaction graphs.  
- Flower: Federated learning coordination and aggregation.  
- NetworkX: Construction and management of transaction graphs.  
- Pandas & NumPy: Data preprocessing and feature engineering.

---

# Test Data and Data Preparation

## Test Data Source

- The Elliptic++ dataset is used as the primary data source for this research.  
  https://github.com/git-disl/EllipticPlusPlus  
- The dataset represents a large-scale transaction graph derived from blockchain activity, with labeled illicit and licit transactions.  
- It is selected due to its suitability for graph-based fraud detection and temporal analysis.

## CBDC-like Simulation Assumption

- The dataset is used as a proxy to simulate CBDC transaction behavior.  
- Wallet addresses are treated as CBDC accounts, and transactions represent digital currency transfers.  
- Fraud labels are mapped to illicit activity within a regulated digital payment context.

## Data Preparation

- Raw transaction data is preprocessed to ensure consistency, completeness, and usability.  
- Transaction records are transformed into graph structures suitable for Graph Neural Network (GNN) training.  
- Temporal information is preserved to reflect evolving transaction behavior over time.  
- Feature normalization and label filtering are applied as part of the preprocessing pipeline.

---

# Research Methodology

## Research Design

- This research adopts a Design Science Research (DSR) approach.  
- The focus is on designing, developing, and evaluating a novel Agentic Federated Learning framework for fraud detection in CBDC networks.  
- The study is applied and experimental, aiming to address real-world privacy and regulatory challenges in digital finance.

## Data Collection

- Primary data source: Elliptic++ transaction graph dataset.  
- The dataset is used to simulate CBDC-like transaction behavior for research purposes.  
- No real customer or institutional data is used.  
- All data used is public, anonymized, and ethically compliant.

## Data Preparation

- Transaction records are preprocessed and transformed into graph-based representations.  
- Temporal information is preserved to reflect evolving fraud patterns.  
- Features are normalized and prepared for graph neural network training.

## AI Model Development

- Graph Neural Networks (GNNs) are used to learn relational fraud patterns from transaction graphs.  
- Models are trained locally at simulated Bank Nodes using institution-specific data.  
- Federated Learning is applied to aggregate model updates without sharing raw transaction data.  
- Agentic components manage training coordination, participation, and adaptive learning behavior.

## Model Evaluation

- Model performance is evaluated using standard fraud detection metrics such as:  
  - Precision  
  - Recall  
  - F1-score  
  - ROC-AUC  
- Evaluation focuses on effectiveness, privacy preservation, and adaptability rather than absolute prediction accuracy.

---

# Ethical Considerations

- The research uses publicly available datasets only.  
- No personally identifiable or sensitive financial data is processed.  
- The system design aligns with privacy-by-design principles and relevant regulatory requirements.

---

# Work Plan

This section outlines the structured plan for the design, development, and evaluation of the proposed Agentic Federated Learning framework for privacy-preserving fraud detection in CBDC networks. The work plan follows an applied research approach, combining literature-driven analysis, system design, model development, and experimental evaluation. Activities are organized sequentially to ensure feasibility within the academic timeframe while allowing iterative refinement.

## Time Line

| Phase | Activity | Description | Duration | Timeline |
|------:|----------|-------------|----------|----------|
| 1 | Project Kickoff & Planning | Finalize scope, milestones, and supervisor alignment | 1 week | Early Feb 2026 |
| 2 | Literature Review | Review CBDCs, fraud detection, FL, GNNs, and agentic AI | 4 weeks | Feb – Early Mar 2026 |
| 3 | Requirement Analysis | Identify functional, technical, privacy, and regulatory needs | 2 weeks | Mar 2026 |
| 4 | Scope & Risk Definition | Refine objectives and identify key risks | 1 week | Late Mar 2026 |
| 5 | Dataset Selection | Review Elliptic++ dataset and define CBDC simulation assumptions | 1 week | Early Apr 2026 |
| 6 | Data Preparation | Data cleaning, feature preparation, and graph construction | 2 weeks | Apr 2026 |
| 7 | System Architecture Design | Design federated architecture and agentic workflow | 2 weeks | Late Apr 2026 |
| 8 | Model Design | Design GNN-based fraud detection model | 2 weeks | Early May 2026 |
| 9 | Local Model Implementation | Implement and validate local GNN models | 3 weeks | May – Early Jun 2026 |
| 10 | Federated Learning Setup | Configure FL workflow and aggregation strategy | 3 weeks | Jun 2026 |
| 11 | Agentic Coordination Implementation | Implement agentic coordinator and local agents | 3 weeks | Jun – Early Jul 2026 |
| 12 | System Integration | Integrate GNN, FL, and agentic components | 2 weeks | Mid Jul 2026 |
| 13 | Testing & Debugging | Functional testing and system stabilization | 2 weeks | Late Jul 2026 |
| 14 | Experimental Evaluation | Evaluate fraud detection and privacy behavior | 3 weeks | Aug 2026 |
| 15 | Result Analysis | Analyze experimental results and findings | 2 weeks | Late Aug 2026 |
| 16 | Validation & Refinement | Validate results and refine system | 2 weeks | Early Sep 2026 |
| 17 | Dissertation Writing | Finalize dissertation chapters | 3 weeks | Sep 2026 |
| 18 | Final Review & Formatting | Proofreading, formatting, and final checks | 1 week | Late Sep 2026 |
| 19 | Final Submission | Dissertation submission | 1 week | End of Sep 2026 |

---

# Deliverables

1) **Approved Project Proposal**  
A formal document defining the research problem, objectives, methodology, and work plan.

2) **Agentic Federated Learning Prototype**  
A functional proof-of-concept demonstrating privacy-preserving fraud detection using federated learning and graph neural networks in a simulated CBDC environment.

3) **Experimental Evaluation Results**  
Quantitative and qualitative evaluation of the proposed framework, demonstrating effectiveness and feasibility.

4) **Final MSc Dissertation**  
A comprehensive written report documenting the research background, methodology, system design, experimental results, discussion, and conclusions.

---

# Expected Outcomes and Limitations

## Expected Outcomes
- The research is expected to demonstrate the feasibility of an agentic federated learning framework for fraud detection in CBDC environments.  
- The proposed approach aims to show how collaborative learning can be achieved without sharing sensitive transaction data.  
- The system is expected to support adaptive and privacy-preserving fraud detection under regulatory constraints.

## Limitations
- The evaluation is based on simulated CBDC behavior using public datasets rather than real central bank data.  
- Performance may be influenced by data heterogeneity and limited label availability.  
- The prototype focuses on technical feasibility rather than full-scale production deployment.

## Future Work
- Extension to real CBDC pilot environments.  
- Exploration of advanced privacy techniques and governance mechanisms.  
- Long-term evaluation under concept drift and evolving fraud patterns.

---

# References

Arner, D. W., Auer, R. & Frost, J., 2020. Central bank digital currencies: a new tool in the financial system. Bank for International Settlements Quarterly Review.  

Bagdasaryan, E. et al., 2020. How to backdoor federated learning. Proceedings of the 23rd International Conference on Artificial Intelligence and Statistics (AISTATS).  

Beutel, A. et al., 2017. Data poisoning attacks against federated learning. Proceedings of the 26th USENIX Security Symposium.  

Brunnermeier, M. K. & Niepelt, D., 2019. On the equivalence of private and public money. Journal of Monetary Economics, pp. 27–41.  

Buterin, V., 2017. On public and private blockchains. Ethereum Foundation Blog.  

Central Bank of England, 2023. The digital pound: a new form of money for households and businesses. Bank of England Discussion Paper.  

Dwork, C. & Roth, A., 2014. The algorithmic foundations of differential privacy. Foundations and Trends in Theoretical Computer Science, 9(3–4), pp. 211–407.  

Hardy, S., Henecka, W., Ivey-Law, H. & Nock, R., 2017. Private federated learning on vertically partitioned data via entity resolution and additive secret sharing. arXiv preprint arXiv:1711.10677.  

Kairouz, P. et al., 2021. Advances and open problems in federated learning. Foundations and Trends in Machine Learning, 14(1–2), pp. 1–210.  

Kipf, T. N. & Welling, M., 2017. Semi-supervised classification with graph convolutional networks. Proceedings of the International Conference on Learning Representations (ICLR).  

Liu, Y. et al., 2018. Detecting fraud in networks using graph neural networks. Proceedings of the 27th ACM International Conference on Information and Knowledge Management.  

Monnerat, J. et al., 2023. Elliptic++: A graph network of Bitcoin blockchain transactions and wallet addresses. arXiv preprint arXiv:2306.06108.  

Organization for Economic Co-operation and Development (OECD), 2023. Central bank digital currencies and financial stability. OECD Policy Paper.  

Shokri, R. & Shmatikov, V., 2015. Privacy-preserving deep learning. Proceedings of the 22nd ACM SIGSAC Conference on Computer and Communications Security.  

Zhang, Q., Chen, C., Li, H. & Li, Z., 2021. Privacy-preserving fraud detection using federated learning. IEEE Transactions on Industrial Informatics, 17(11), pp. 7619–7628.  
