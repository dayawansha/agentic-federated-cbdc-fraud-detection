# Local GNN Model

Graph Neural Network (GNN) engine performing local training, loss optimization, model evaluation, and fraud inference.

## Port
- **`9002`** (REST API)

## Service Responsibilities
The `local-gnn-model` is the **AI engine (analytical brain)** of the bank node. It is responsible for training the machine learning models and detecting suspicious activity on the bank's transaction graph.

1. **AI Model Architectures**
   - **What it does:** Hosts the graph neural network code that understands complex transaction networks.
   - **How it works:** It supports multiple network architectures (like GCN, GAT, GraphSAGE, and a skip-connected `HYBRID` model) that look at both transaction properties and connections between bank accounts to identify fraud patterns.

2. **Training the Local Model**
   - **What it does:** Fine-tunes the global AI model using the bank's local transaction records.
   - **How it works:** It receives the starting weights from the coordinator, runs optimization iterations (epochs) over the bank's private data, and calculates the updated weight tensors.

3. **Spotting Suspicious Activity (Fraud Inference)**
   - **What it does:** Scans new bank transactions to assign a probability of fraud to them.
   - **How it works:** It analyzes transaction features (amount, timestamp, sending/receiving patterns) and estimates the likelihood that a transaction is part of an illegal money laundering ring or structuring attempt.

4. **Evaluating Performance Stats**
   - **What it does:** Measures how well the AI model is performing at detecting fraud locally.
   - **How it works:** It calculates evaluation statistics including loss, accuracy, precision, recall, F1-score, and AUC-ROC, so the coordinator knows how much to trust the bank's updates.

---

## API Endpoints

### 1. General & Utility
- `GET /health`: Returns basic health status.

### 2. Deep Learning Operations
- `POST /train`: Executes training epochs.
  - **Payload**: Includes base64-encoded initial model weights, learning rate, batch size, epoch counts, target file paths, and model type parameters (`HYBRID`, `GCN`, `GAT`, `SAGE`).
  - **Response**: Returns base64-encoded trained weights, sample size, and performance metrics.
- `POST /infer`: Computes fraud probabilities.
  - **Payload**: Includes model weights and inference dataset path.
  - **Response**: List of predicted nodes, probabilities, and labels (0 = licit, 1 = illicit, 2 = unknown).

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TX_SHARD_PATH` | Directory containing transaction CSV shards | `/app/train-data/processed` |
| `GRAPH_LIMIT`   | Maximum number of node inputs processed during data loading | `300` |

---

## Technology Stack
- **Deep Learning Framework**: PyTorch, PyTorch Geometric (PyG)
- **Framework**: FastAPI, Uvicorn, Pydantic
- **Data Science Stack**: Pandas, NumPy, Scikit-learn
