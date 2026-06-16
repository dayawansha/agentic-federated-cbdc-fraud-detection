# Local GNN Model

Graph Neural Network (GNN) engine performing local training, loss optimization, model evaluation, and fraud inference.

## Port
- **`9002`** (REST API)

## Service Responsibilities
The `local-gnn-model` service encapsulates the deep learning routines of the bank node, leveraging structural and relational data to identify illicit transaction patterns.

- **Hybrid GNN Architectures**: Supports multiple model architectures including Graph Convolutional Networks (GCN), Graph Attention Networks (GAT), GraphSAGE, and a skip-connected `HYBRID` model combining SAGE and GAT layers with layer normalization.
- **Local Model Training**: Accepts starting global model weights, constructs local datasets, runs training epochs (optimizing cross-entropy loss), and returns local update tensors.
- **Fraud Inference**: Evaluates transaction node characteristics (amounts, timestamps, degree centralities) and computes fraud probability predictions.
- **Metric Evaluation**: Measures local model classification performance using metrics such as loss, accuracy, precision, recall, F1-score, and AUC-ROC.

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
