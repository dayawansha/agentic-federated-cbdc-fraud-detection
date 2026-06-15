import logging
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from torch_geometric.data import Data

from src.model import get_model
from src.trainer import LocalTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrainRequest(BaseModel):
    round_id: Optional[str] = None
    global_weights: Optional[bytes] = None
    epochs: int = 1

class TrainResponse(BaseModel):
    status: str
    weights: bytes
    sample_size: int
    metrics: Dict[str, float]


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
    edge_index = torch.tensor([src, dst], dtype=torch.long)
    rev_edge_index = torch.tensor([dst, src], dtype=torch.long)
    edge_index = torch.cat([edge_index, rev_edge_index], dim=1)

    return Data(x=x, edge_index=edge_index, y=y)

@lru_cache(maxsize=1)
def _init_trainer() -> LocalTrainer:
    data = _load_graph_data()
    model_type = os.getenv("MODEL_TYPE", "SAGE")
    hidden_dim = int(os.getenv("HIDDEN_DIM", "64"))
    output_dim = int(os.getenv("OUTPUT_DIM", "3"))
    model = get_model(input_dim=data.x.shape[1], hidden_dim=hidden_dim, output_dim=output_dim, model_type=model_type)
    lr = float(os.getenv("LR", "0.01"))
    weight_decay = float(os.getenv("WEIGHT_DECAY", "0.0005"))
    return LocalTrainer(model=model, lr=lr, weight_decay=weight_decay)

@app.post("/train")
async def trigger_training(request: TrainRequest) -> TrainResponse:
    try:
        trainer = _init_trainer()
        data = _load_graph_data()
        if request.global_weights:
            trainer.set_model_weights(request.global_weights)

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
        return TrainResponse(status="training_completed", weights=weights, sample_size=int(labeled), metrics=metrics)
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002)
