import torch
import torch.nn.functional as F
import logging

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
        class_weights = self._compute_class_weights(data.y[mask], num_classes=out.shape[1])
        loss = F.nll_loss(out[mask], data.y[mask], weight=class_weights)
        loss.backward()
        self.optimizer.step()
        return loss.item()

    def evaluate(self, data):
        self.model.eval()
        data = data.to(self.device)
        with torch.no_grad():
            log_probs = self.model(data.x, data.edge_index)
            probs = torch.exp(log_probs)
            pred = probs.argmax(dim=1)

            mask = (data.y == 0) | (data.y == 1)
            y_true = data.y[mask]
            y_pred = pred[mask]
            positive_scores = probs[mask][:, 1]

            labeled_count = int(mask.sum().item())
            if labeled_count == 0:
                return {
                    "accuracy": 0.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1_score": 0.0,
                    "roc_auc": 0.0,
                    "labeled_samples": 0.0,
                }

            tp = int(((y_pred == 1) & (y_true == 1)).sum().item())
            tn = int(((y_pred == 0) & (y_true == 0)).sum().item())
            fp = int(((y_pred == 1) & (y_true == 0)).sum().item())
            fn = int(((y_pred == 0) & (y_true == 1)).sum().item())

            acc = (tp + tn) / labeled_count if labeled_count else 0.0
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
            roc_auc = self._binary_roc_auc_score(y_true.cpu().tolist(), positive_scores.cpu().tolist())

        return {
            "accuracy": float(acc),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1_score),
            "roc_auc": float(roc_auc),
            "labeled_samples": float(labeled_count),
        }

    def _compute_class_weights(self, labels, num_classes=2):
        label_tensor = labels.detach()
        counts = torch.bincount(label_tensor, minlength=num_classes).float()
        counts = torch.clamp(counts, min=1.0)
        weights = counts.sum() / (counts * counts.numel())
        return weights.to(self.device)

    @staticmethod
    def _binary_roc_auc_score(y_true, y_score):
        positives = sum(1 for label in y_true if int(label) == 1)
        negatives = sum(1 for label in y_true if int(label) == 0)
        if positives == 0 or negatives == 0:
            return 0.0

        ranked = sorted(zip(y_score, y_true), key=lambda item: item[0])
        sum_positive_ranks = 0.0
        index = 0
        while index < len(ranked):
            end = index
            score = ranked[index][0]
            while end + 1 < len(ranked) and ranked[end + 1][0] == score:
                end += 1

            average_rank = (index + end + 2) / 2.0
            for cursor in range(index, end + 1):
                if int(ranked[cursor][1]) == 1:
                    sum_positive_ranks += average_rank
            index = end + 1

        return (sum_positive_ranks - (positives * (positives + 1) / 2.0)) / (positives * negatives)

    def predict(self, data):
        self.model.eval()
        data = data.to(self.device)
        with torch.no_grad():
            log_probs = self.model(data.x, data.edge_index)
            probs = torch.exp(log_probs)
            pred = probs.argmax(dim=1)
        return {
            "predictions": pred.cpu(),
            "probabilities": probs.cpu(),
        }

    def get_model_weights(self) -> bytes:
        import io
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        return buffer.getvalue()

    def set_model_weights(self, weights_bytes: bytes):
        import io
        buffer = io.BytesIO(weights_bytes)
        self.model.load_state_dict(torch.load(buffer))
