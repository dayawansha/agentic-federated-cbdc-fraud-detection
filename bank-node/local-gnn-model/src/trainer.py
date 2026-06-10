import torch
import torch.nn.functional as F
import logging
from typing import Dict
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalTrainer:
    def __init__(self, model, lr=0.01, weight_decay=5e-4):
        self.model = model
        self.optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def train_epoch(self, data):
        self.model.train()
        self.optimizer.zero_grad()
        
        # data should be a PyG Data object
        data = data.to(self.device)
        out = self.model(data.x, data.edge_index)
        
        # Only train on nodes with known labels (class 1 and 2)
        # In Elliptic dataset, class 3 is unknown
        mask = (data.y == 0) | (data.y == 1) # Assuming labels mapped to 0, 1
        
        loss = F.nll_loss(out[mask], data.y[mask])
        loss.backward()
        self.optimizer.step()
        return loss.item()

    def evaluate(self, data):
        self.model.eval()
        data = data.to(self.device)
        with torch.no_grad():
            out = self.model(data.x, data.edge_index)
            pred = out.argmax(dim=1)
            
            mask = (data.y == 0) | (data.y == 1)
            correct = (pred[mask] == data.y[mask]).sum().item()
            acc = correct / mask.sum().item()
            
        return {"accuracy": acc}

    def get_model_weights(self) -> bytes:
        import io
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        return buffer.getvalue()

    def set_model_weights(self, weights_bytes: bytes):
        import io
        buffer = io.BytesIO(weights_bytes)
        self.model.load_state_dict(torch.load(buffer))
