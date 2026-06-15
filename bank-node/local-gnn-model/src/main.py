import logging
import os
import base64
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

class TrainRequest(BaseModel):
    round_id: Optional[str] = None
    global_weights: Optional[str] = None
    epochs: int = 1

class TrainResponse(BaseModel):
    status: str
    weights: str
    sample_size: int
    metrics: Dict[str, float]


class InferenceRequest(BaseModel):
    tx_ids: Optional[List[int]] = None
    global_weights: Optional[str] = None
    limit: int = 20


class InferencePrediction(BaseModel):
    tx_id: int
    predicted_class: str
    predicted_label: int
    confidence: float
    illicit_probability: float
    licit_probability: float
    unknown_probability: float
    known_label: Optional[str] = None


class InferenceResponse(BaseModel):
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        _ = _init_trainer()
        logger.info("Local GNN trainer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Local GNN trainer: {e}")
    yield


app = FastAPI(title="Local GNN Model Service", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@lru_cache(maxsize=1)
def _load_graph_data() -> Data:
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

    x = torch.tensor(nodes_df[feature_cols].to_numpy(dtype="float32"), dtype=torch.float32)

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

    return Data(x=x, edge_index=edge_index, y=y, tx_ids=tx_ids)

@lru_cache(maxsize=1)
def _init_trainer() -> LocalTrainer:
    data = _load_graph_data()
    model_type = os.getenv("MODEL_TYPE", "HYBRID")
    hidden_dim = int(os.getenv("HIDDEN_DIM", "64"))
    output_dim = int(os.getenv("OUTPUT_DIM", "3"))
    num_heads = int(os.getenv("MODEL_HEADS", "4"))
    dropout = float(os.getenv("MODEL_DROPOUT", "0.3"))
    model = get_model(
        input_dim=data.x.shape[1],
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
    try:
        trainer = _init_trainer()
        data = _load_graph_data()
        if request.global_weights:
            trainer.set_model_weights(base64.b64decode(request.global_weights))

        epochs = max(1, int(request.epochs))
        last_loss = None
        for _ in range(epochs):
            last_loss = trainer.train_epoch(data)

        metrics = trainer.evaluate(data)
        if last_loss is not None:
            metrics["loss"] = float(last_loss)

        y = data.y
        labeled = ((y == 0) | (y == 1)).sum().item()
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
    try:
        trainer = _init_trainer()
        data = _load_graph_data()
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
