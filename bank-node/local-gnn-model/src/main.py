"""
================================================================================
LOCAL GNN MODEL SERVICE - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Local GNN (Graph Neural Network) Model service as the bank's "Expert Detective"
that spots suspicious financial networks.

Traditional fraud filters only look at single transactions in isolation (e.g., flagging
any transfer over $10,000). But real money launderers and fraudsters split payments
among dozens of intermediate accounts (layering). 

A GNN represents transactions as a web:
- Nodes: Accounts and transactions.
- Edges: Transfers of money (from account to transaction, or transaction to account).
By looking at the shape and connection patterns of the web, the GNN learns to spot
illicit patterns that rule-based systems miss.

MAIN RESPONSIBILITIES:
1. TRAINING: Under federated orchestrations, it updates the weights of a PyTorch Geometric
   model using local graph files or live Neo4j database exports.
2. PSEUDO-LABELING FOR SPARSE LABELS: In real banking, only a tiny fraction of transactions
   are audited and labeled as "licit" or "illicit". Most are "unknown".
   To avoid ignoring this massive amount of data, the service uses the GNN to make
   high-confidence guesses (pseudo-labels) on unknown transactions, and trains on them
   with an adjusted weight, boosting model resilience.
3. INFERENCE (DETECTION): It scores incoming transactions and calculates the probability
   that they are safe, fraudulent, or unknown, which is then used to trigger alerts.
================================================================================
"""
import logging
import os
import base64
import re
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from torch_geometric.data import Data

from src.model import get_model
from src.trainer import LocalTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LABEL_NAMES = {
    0: "licit",
    1: "illicit",
    2: "unknown",
}

LIVE_GRAPH_MIN_LABELED_NODES = max(1, int(os.getenv("LIVE_GRAPH_MIN_LABELED_NODES", "1")))
DEFAULT_PSEUDO_LABEL_WEIGHT = float(os.getenv("PSEUDO_LABEL_WEIGHT", "0.35"))
DEFAULT_PSEUDO_LABEL_CONFIDENCE = float(os.getenv("PSEUDO_LABEL_CONFIDENCE", "0.9"))


def _append_structural_features(x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
    num_nodes = int(x.shape[0])
    if num_nodes == 0:
        return x

    src = edge_index[0]
    dst = edge_index[1]
    out_degree = torch.bincount(src, minlength=num_nodes).float()
    in_degree = torch.bincount(dst, minlength=num_nodes).float()
    total_degree = in_degree + out_degree
    degree_scale = torch.clamp(total_degree.max(), min=1.0)

    structural = torch.stack(
        [
            in_degree / degree_scale,
            out_degree / degree_scale,
            total_degree / degree_scale,
            (out_degree - in_degree).abs() / degree_scale,
        ],
        dim=1,
    )
    return torch.cat([x, structural.to(dtype=x.dtype)], dim=1)

# BUSINESS REASON: These schema classes define the structured contracts (request and response shapes)
# used to control the local training and inference execution on GNN transaction networks.

class TrainRequest(BaseModel):
    """
    BUSINESS REASON: Transports training hyper-parameters to start a local training run.
    - 'round_id': Tracks the current collaborative federated learning round.
    - 'global_weights': The global GNN model parameters to load before training.
    - 'epochs': The number of passes through the training graph dataset.
    - 'strategy': The aggregation method being used (e.g. FedAvg or FedProxGNN).
    - 'fedprox_mu': The regularizing penalty weight (if strategy is FedProxGNN).
    - 'pseudo_label_weight': The weight given to self-labeled guesses when data is sparse.
    - 'pseudo_label_confidence': The probability threshold for self-labeled guesses.
    """
    round_id: Optional[str] = None
    global_weights: Optional[str] = None
    epochs: int = 1
    strategy: str = "FedAvg"
    fedprox_mu: Optional[float] = None
    pseudo_label_weight: Optional[float] = None
    pseudo_label_confidence: Optional[float] = None

class TrainResponse(BaseModel):
    """
    BUSINESS REASON: Returns the locally updated GNN weights and training metrics
    to be aggregated by the central coordinator.
    - 'weights': The trained GNN parameters (base64).
    - 'sample_size': The number of training samples used.
    - 'metrics': Statistics like accuracy, loss, and graph characteristics.
    """
    status: str
    weights: str
    sample_size: int
    metrics: Dict[str, float]


class InferenceRequest(BaseModel):
    """
    BUSINESS REASON: Requests fraud evaluation for a set of transactions.
    - 'tx_ids': The list of transaction IDs to investigate. If omitted, rank by risk.
    - 'global_weights': The global model weights to apply.
    - 'limit': The maximum number of risk predictions to return.
    """
    tx_ids: Optional[List[int]] = None
    global_weights: Optional[str] = None
    limit: int = 20


class InferencePrediction(BaseModel):
    """
    BUSINESS REASON: Represents the GNN risk prediction for a single transaction.
    - 'tx_id': The transaction ID.
    - 'predicted_class': 'licit' (safe), 'illicit' (fraud), or 'unknown'.
    - 'predicted_label': Numeric label corresponding to class.
    - 'confidence': Probability score of the top predicted class.
    - 'illicit_probability': GNN probability that the transaction is fraud.
    """
    tx_id: int
    predicted_class: str
    predicted_label: int
    confidence: float
    illicit_probability: float
    licit_probability: float
    unknown_probability: float
    known_label: Optional[str] = None


class InferenceResponse(BaseModel):
    """
    BUSINESS REASON: Delivers a set of GNN risk predictions to the local agent to publish alerts.
    """
    status: str
    prediction_count: int
    predictions: List[InferencePrediction]


def _resolve_data_file(relative_path: str, env_var: str) -> str:
    override = os.getenv(env_var)
    if override:
        return override

    service_root = Path(__file__).resolve().parents[1]
    candidate_roots = [service_root, *service_root.parents]

    for root in candidate_roots:
        candidate = root / relative_path
        if candidate.exists():
            return str(candidate)

    # Default to the service-root-relative location inside the container image.
    return str(service_root / relative_path)
def _resolve_default_paths() -> Dict[str, str]:
    return {
        "shard_path": os.getenv(
            "TX_SHARD_PATH", _resolve_data_file("train-data/processed/txs_shard_1.csv", "TX_SHARD_PATH")
        ),
        "edges_path": os.getenv(
            "TX_EDGES_PATH", _resolve_data_file("train-data/processed/txs_edges_processed.csv", "TX_EDGES_PATH")
        ),
        "classes_path": os.getenv(
            "TX_CLASSES_PATH",
            _resolve_data_file(
                "train-data/EllipticPlusPlus-main/Transactions Dataset/txs_classes.csv",
                "TX_CLASSES_PATH",
            ),
        ),
    }


def _extract_numeric_transaction_id(node_id: object) -> int:
    text = str(node_id)
    try:
        return int(text)
    except ValueError:
        matches = re.findall(r"\d+", text)
        if matches:
            return int(matches[-1])
        raise ValueError(f"Unable to derive numeric transaction id from {text}")


def _load_label_map() -> Dict[int, int]:
    paths = _resolve_default_paths()
    classes_path = paths["classes_path"]
    classes_df = pd.read_csv(classes_path)
    classes_df["txId"] = classes_df["txId"].astype("int64")
    return dict(zip(classes_df["txId"].tolist(), classes_df["class"].tolist()))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        data = _load_graph_data()
        _ = _init_trainer(int(data.x.shape[1]))
        logger.info("Local GNN trainer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Local GNN trainer: {e}")
    yield


app = FastAPI(title="Local GNN Model Service", lifespan=lifespan)

@app.get("/health")
async def health_check():
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the local agent or orchestrators
    to check the health of the local GNN training service, ensuring it is ready to process
    training or prediction requests.
    """
    return {"status": "healthy"}

import httpx
TRANSACTION_GRAPH_URL = os.getenv("TRANSACTION_GRAPH_URL", "http://localhost:9004")

def _load_live_graph_data() -> Optional[Data]:
    """
    Attempts to fetch live graph data from transaction-graph service.
    Returns None if empty, offline, or upon error.
    """
    logger.info("Attempting to load live graph data from Transaction Graph Service...")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{TRANSACTION_GRAPH_URL}/graph/export-tensors")
            if response.status_code != 200:
                logger.warning(f"Transaction Graph Service returned code {response.status_code}")
                return None
            
            payload = response.json()
            if str(payload.get("status", "success")).lower() != "success":
                logger.warning("Transaction Graph export did not report success status")
                return None
            if str(payload.get("node_type", "transaction")).lower() != "transaction":
                logger.warning("Transaction Graph export is not transaction-aligned, falling back to static CSV shard")
                return None
            node_ids = payload.get("node_ids", [])
            x_raw = payload.get("x", [])
            edge_index_raw = payload.get("edge_index", [[], []])
            feature_names = payload.get("feature_names", [])

            if not node_ids or not x_raw:
                logger.warning("Live graph database is empty, falling back to static CSV shard")
                return None

            logger.info(
                "Successfully fetched live transaction graph: %s nodes, %s edges, %s exported features",
                len(node_ids),
                len(edge_index_raw[0]) if edge_index_raw and len(edge_index_raw) >= 2 else 0,
                len(feature_names),
            )

            x = torch.tensor(x_raw, dtype=torch.float32)
            label_map = _load_label_map()

            y_vals = []
            tx_ids = []
            for node_id in node_ids:
                try:
                    tx_id = _extract_numeric_transaction_id(node_id)
                except ValueError:
                    logger.warning("Skipping live graph payload because node id %s is not transaction-like", node_id)
                    return None

                tx_ids.append(tx_id)
                c = int(label_map.get(tx_id, 3))
                if c == 1:
                    y_vals.append(1)
                elif c == 2:
                    y_vals.append(0)
                else:
                    y_vals.append(2)

            labeled_count = sum(1 for label in y_vals if label in {0, 1})
            sparse_label_mode = labeled_count < LIVE_GRAPH_MIN_LABELED_NODES
            if sparse_label_mode:
                logger.warning(
                    "Live transaction graph only contains %s labeled transactions; enabling sparse-label semi-supervised mode",
                    labeled_count,
                )

            y = torch.tensor(y_vals, dtype=torch.long)

            if edge_index_raw and len(edge_index_raw) == 2:
                edge_index = torch.tensor(edge_index_raw, dtype=torch.long)
            else:
                edge_index = torch.empty((2, 0), dtype=torch.long)

            if edge_index.shape[1] > 0:
                rev_edge_index = torch.stack([edge_index[1], edge_index[0]], dim=0)
                edge_index = torch.cat([edge_index, rev_edge_index], dim=1)

            x = _append_structural_features(x, edge_index)
            data = Data(x=x, edge_index=edge_index, y=y, tx_ids=tx_ids)
            data.data_source = "live"
            data.live_graph_used = True
            data.sparse_label_mode = sparse_label_mode
            data.labeled_count = int(labeled_count)
            data.unlabeled_count = int(len(y_vals) - labeled_count)
            data.exported_feature_count = int(len(feature_names))
            return data
            
    except Exception as e:
        logger.warning(f"Failed to fetch live graph from Transaction Graph: {e}. Falling back to static CSV shard.")
        return None

@lru_cache(maxsize=1)
def _load_static_graph_data() -> Data:
    paths = _resolve_default_paths()
    shard_path = paths["shard_path"]
    edges_path = paths["edges_path"]
    classes_path = paths["classes_path"]

    max_nodes_env = os.getenv("MAX_NODES")
    max_nodes = int(max_nodes_env) if max_nodes_env else None

    nodes_df = pd.read_csv(shard_path)
    if max_nodes is not None and max_nodes > 0 and len(nodes_df) > max_nodes:
        nodes_df = nodes_df.iloc[:max_nodes].copy()

    if "txId" not in nodes_df.columns:
        raise ValueError("Shard file missing required txId column")

    tx_ids = nodes_df["txId"].astype("int64").tolist()
    feature_cols = [c for c in nodes_df.columns if c not in {"txId", "Time step"}]
    if not feature_cols:
        raise ValueError("Shard file has no feature columns")

    x = torch.tensor(nodes_df[feature_cols].fillna(0.0).to_numpy(dtype="float32"), dtype=torch.float32)

    classes_df = pd.read_csv(classes_path)
    classes_df["txId"] = classes_df["txId"].astype("int64")
    label_map = dict(zip(classes_df["txId"].tolist(), classes_df["class"].tolist()))

    y_vals = []
    for tx_id in tx_ids:
        c = int(label_map.get(tx_id, 3))
        if c == 1:
            y_vals.append(1)
        elif c == 2:
            y_vals.append(0)
        else:
            y_vals.append(2)
    y = torch.tensor(y_vals, dtype=torch.long)

    idx_map = {tx_id: i for i, tx_id in enumerate(tx_ids)}

    edges_df = pd.read_csv(edges_path)
    edges_df["txId1"] = edges_df["txId1"].astype("int64")
    edges_df["txId2"] = edges_df["txId2"].astype("int64")

    mask = edges_df["txId1"].isin(idx_map) & edges_df["txId2"].isin(idx_map)
    edges_df = edges_df.loc[mask]

    if len(edges_df) == 0:
        raise ValueError("No edges found after filtering to shard nodes")

    src = edges_df["txId1"].map(idx_map).to_numpy(dtype="int64")
    dst = edges_df["txId2"].map(idx_map).to_numpy(dtype="int64")
    edge_index = torch.from_numpy(np.stack((src, dst))).to(dtype=torch.long)
    rev_edge_index = torch.from_numpy(np.stack((dst, src))).to(dtype=torch.long)
    edge_index = torch.cat([edge_index, rev_edge_index], dim=1)
    x = _append_structural_features(x, edge_index)
    labeled_count = sum(1 for label in y_vals if label in {0, 1})
    data = Data(x=x, edge_index=edge_index, y=y, tx_ids=tx_ids)
    data.data_source = "static"
    data.live_graph_used = False
    data.sparse_label_mode = False
    data.labeled_count = int(labeled_count)
    data.unlabeled_count = int(len(y_vals) - labeled_count)
    data.exported_feature_count = int(len(feature_cols))
    return data

def _load_graph_data() -> Data:
    live_data = _load_live_graph_data()
    if live_data is not None:
        return live_data
    return _load_static_graph_data()

@lru_cache(maxsize=4)
def _init_trainer(input_dim: int) -> LocalTrainer:
    model_type = os.getenv("MODEL_TYPE", "HYBRID")
    hidden_dim = int(os.getenv("HIDDEN_DIM", "64"))
    output_dim = int(os.getenv("OUTPUT_DIM", "3"))
    num_heads = int(os.getenv("MODEL_HEADS", "4"))
    dropout = float(os.getenv("MODEL_DROPOUT", "0.3"))
    model = get_model(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        output_dim=output_dim,
        model_type=model_type,
        num_heads=num_heads,
        dropout=dropout,
    )
    lr = float(os.getenv("LR", "0.01"))
    weight_decay = float(os.getenv("WEIGHT_DECAY", "0.0005"))
    return LocalTrainer(model=model, lr=lr, weight_decay=weight_decay)


def _format_prediction(tx_id: int, predicted_label: int, probabilities: torch.Tensor, known_label: Optional[int]) -> InferencePrediction:
    return InferencePrediction(
        tx_id=int(tx_id),
        predicted_class=LABEL_NAMES.get(int(predicted_label), "unknown"),
        predicted_label=int(predicted_label),
        confidence=float(probabilities[int(predicted_label)].item()),
        illicit_probability=float(probabilities[1].item()),
        licit_probability=float(probabilities[0].item()),
        unknown_probability=float(probabilities[2].item()),
        known_label=LABEL_NAMES.get(int(known_label)) if known_label is not None else None,
    )

@app.post("/train")
async def trigger_training(request: TrainRequest) -> TrainResponse:
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the Local Agent during a federated learning
    round. It initiates GNN model training on the bank's local transaction graph. The business goal is
    to allow the GNN model to adjust its parameters to match local transaction characteristics while
    using strategies like FedProx and pseudo-labeling.
    """
    try:
        data = _load_graph_data()
        trainer = _init_trainer(int(data.x.shape[1]))
        training_strategy = str(request.strategy or "FedAvg")
        fedprox_mu = float(request.fedprox_mu) if request.fedprox_mu is not None else float(os.getenv("FEDPROX_MU", "1.0"))
        pseudo_label_weight = (
            float(request.pseudo_label_weight)
            if request.pseudo_label_weight is not None
            else DEFAULT_PSEUDO_LABEL_WEIGHT
        )
        pseudo_label_confidence = (
            float(request.pseudo_label_confidence)
            if request.pseudo_label_confidence is not None
            else DEFAULT_PSEUDO_LABEL_CONFIDENCE
        )
        sparse_label_mode = bool(getattr(data, "sparse_label_mode", False))
        trainer.configure_training(
            strategy=training_strategy,
            fedprox_mu=fedprox_mu,
            sparse_label_mode=sparse_label_mode,
            pseudo_label_weight=pseudo_label_weight,
            pseudo_label_confidence=pseudo_label_confidence,
        )
        if request.global_weights:
            trainer.set_model_weights(base64.b64decode(request.global_weights))
        if training_strategy == "FedProxGNN":
            trainer.capture_proximal_reference()
        else:
            trainer.clear_proximal_reference()

        epochs = max(1, int(request.epochs))
        last_loss = None
        for _ in range(epochs):
            last_loss = trainer.train_epoch(data)

        metrics = trainer.evaluate(data)
        if last_loss is not None:
            metrics["loss"] = float(last_loss)
        if training_strategy == "FedProxGNN":
            metrics["fedprox_mu"] = float(fedprox_mu)
            metrics["fedprox_base_loss"] = float(getattr(trainer, "last_base_loss", 0.0))
            metrics["fedprox_penalty"] = float(getattr(trainer, "last_proximal_penalty", 0.0))
        metrics["pseudo_label_weight"] = float(pseudo_label_weight)
        metrics["pseudo_label_confidence"] = float(pseudo_label_confidence)
        metrics["live_graph_used"] = 1.0 if bool(getattr(data, "live_graph_used", False)) else 0.0
        metrics["data_source_live"] = 1.0 if str(getattr(data, "data_source", "static")) == "live" else 0.0
        metrics["sparse_label_mode"] = 1.0 if sparse_label_mode else 0.0
        metrics["unlabeled_samples"] = float(getattr(data, "unlabeled_count", 0))
        metrics["exported_feature_count"] = float(getattr(data, "exported_feature_count", 0))

        y = data.y
        labeled = ((y == 0) | (y == 1)).sum().item()
        node_count = int(data.x.shape[0]) if getattr(data, "x", None) is not None else 0
        edge_count = int(data.edge_index.shape[1]) if getattr(data, "edge_index", None) is not None else 0
        avg_degree = (edge_count / node_count) if node_count else 0.0
        graph_density = (edge_count / max(1, node_count * max(node_count - 1, 1))) if node_count > 1 else 0.0
        labeled_ratio = (float(labeled) / float(node_count)) if node_count else 0.0
        metrics.update(
            {
                "graph_node_count": float(node_count),
                "graph_edge_count": float(edge_count),
                "avg_degree": float(avg_degree),
                "graph_density": float(graph_density),
                "labeled_ratio": float(labeled_ratio),
            }
        )
        weights = trainer.get_model_weights()
        return TrainResponse(
            status="training_completed",
            weights=base64.b64encode(weights).decode("ascii"),
            sample_size=int(labeled),
            metrics=metrics,
        )
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/infer", response_model=InferenceResponse)
async def run_inference(request: InferenceRequest) -> InferenceResponse:
    """
    BUSINESS PURPOSE / REASON: This endpoint is called by the Local Agent to evaluate transaction risk.
    It takes either a specific list of transaction IDs or ranks all local transactions by their likelihood
    of illicit activity. The business goal is to generate risk scores to trigger fraud alert events.
    """
    try:
        data = _load_graph_data()
        trainer = _init_trainer(int(data.x.shape[1]))
        if request.global_weights:
            trainer.set_model_weights(base64.b64decode(request.global_weights))

        prediction_result = trainer.predict(data)
        predictions = prediction_result["predictions"]
        probabilities = prediction_result["probabilities"]
        tx_ids = list(getattr(data, "tx_ids", []))
        labels = data.y.cpu().tolist()

        if not tx_ids:
            raise ValueError("No tx_ids available in loaded graph data")

        tx_index = {int(tx_id): idx for idx, tx_id in enumerate(tx_ids)}
        limit = max(1, int(request.limit))

        if request.tx_ids:
            missing = [int(tx_id) for tx_id in request.tx_ids if int(tx_id) not in tx_index]
            if missing:
                raise HTTPException(status_code=404, detail={"missing_tx_ids": missing})
            selected_indices = [tx_index[int(tx_id)] for tx_id in request.tx_ids]
        else:
            ranked_indices = sorted(
                range(len(tx_ids)),
                key=lambda idx: float(probabilities[idx][1].item()),
                reverse=True,
            )
            selected_indices = ranked_indices[:limit]

        formatted = []
        for idx in selected_indices[:limit]:
            known_label = int(labels[idx]) if int(labels[idx]) in LABEL_NAMES else None
            formatted.append(
                _format_prediction(
                    tx_id=int(tx_ids[idx]),
                    predicted_label=int(predictions[idx].item()),
                    probabilities=probabilities[idx],
                    known_label=known_label,
                )
            )

        return InferenceResponse(
            status="inference_completed",
            prediction_count=len(formatted),
            predictions=formatted,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002)
