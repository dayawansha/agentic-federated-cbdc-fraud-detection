"""
================================================================================
LOCAL TRAINER - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the LocalTrainer as the "study tutor" or "gym coach" for the local GNN detective.
It sets up the learning parameters, manages the optimization loop, and calculates
the mathematical penalties that help the model learn from ledger transactions.

Its key training features are:
1. OPTIMIZATION: Uses the Adam optimizer to fine-tune the model parameters based on
   loss (error rate).
2. REGULARIZATION LEASH (FedProx): If training under a FedProx strategy, the trainer
   computes a "proximal penalty." This penalty acts like a physical leash, preventing
   the local model weights from drifting too far away from the global reference weights.
   This prevents the model from forgetting global knowledge while adapting to local data.
3. PSEUDO-LABEL TRAINING: When labels are sparse, it runs the model on unlabeled transactions.
   If the model is highly confident (e.g. > 90%) about its classification, the trainer
   applies a "pseudo-label" (temporary guess) and feeds it back into training.
   It scales this guest-loss with a modifier (`pseudo_label_weight`) to ensure the
   detective learns from unlabeled patterns without trusting its own guesses blindly.
================================================================================
"""
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
        self.training_strategy = "FedAvg"
        self.fedprox_mu = 0.0
        self.global_reference_params = None
        self.sparse_label_mode = False
        self.pseudo_label_weight = 0.0
        self.pseudo_label_confidence = 0.9
        self.last_base_loss = 0.0
        self.last_proximal_penalty = 0.0
        self.last_pseudo_label_loss = 0.0
        self.last_pseudo_labeled_samples = 0

    def configure_training(
        self,
        strategy: str = "FedAvg",
        fedprox_mu: float = 0.0,
        sparse_label_mode: bool = False,
        pseudo_label_weight: float = 0.0,
        pseudo_label_confidence: float = 0.9,
    ):
        self.training_strategy = str(strategy or "FedAvg")
        self.fedprox_mu = max(0.0, float(fedprox_mu or 0.0))
        self.sparse_label_mode = bool(sparse_label_mode)
        self.pseudo_label_weight = max(0.0, float(pseudo_label_weight or 0.0))
        self.pseudo_label_confidence = min(0.999, max(0.5, float(pseudo_label_confidence or 0.9)))
        self.last_base_loss = 0.0
        self.last_proximal_penalty = 0.0
        self.last_pseudo_label_loss = 0.0
        self.last_pseudo_labeled_samples = 0
        if self.training_strategy != "FedProxGNN":
            self.global_reference_params = None

    def capture_proximal_reference(self):
        self.global_reference_params = {
            name: parameter.detach().clone().to(self.device)
            for name, parameter in self.model.named_parameters()
            if parameter.requires_grad
        }

    def clear_proximal_reference(self):
        self.global_reference_params = None
        self.last_proximal_penalty = 0.0

    def _fedprox_penalty(self):
        if self.training_strategy != "FedProxGNN" or self.fedprox_mu <= 0 or not self.global_reference_params:
            return None

        penalty = None
        for name, parameter in self.model.named_parameters():
            if not parameter.requires_grad:
                continue
            reference = self.global_reference_params.get(name)
            if reference is None:
                continue
            distance = torch.sum((parameter - reference) ** 2)
            penalty = distance if penalty is None else penalty + distance
        if penalty is None:
            return None
        return 0.5 * self.fedprox_mu * penalty

    def _pseudo_label_loss(self, log_probs, data):
        if not self.sparse_label_mode or self.pseudo_label_weight <= 0.0:
            return None, 0

        unlabeled_mask = data.y == 2
        unlabeled_count = int(unlabeled_mask.sum().item())
        if unlabeled_count == 0:
            return None, 0

        unlabeled_log_probs = log_probs[unlabeled_mask]
        unlabeled_probs = torch.exp(unlabeled_log_probs)
        confidences, pseudo_labels = unlabeled_probs.max(dim=1)
        confident_mask = confidences >= self.pseudo_label_confidence

        if unlabeled_probs.shape[1] > 2:
            confident_mask = confident_mask & (pseudo_labels != 2)

        confident_count = int(confident_mask.sum().item())
        if confident_count == 0:
            return None, 0

        pseudo_loss = F.nll_loss(unlabeled_log_probs[confident_mask], pseudo_labels[confident_mask])
        return pseudo_loss * self.pseudo_label_weight, confident_count

    def train_epoch(self, data):
        self.model.train()
        self.optimizer.zero_grad()
        
        # data should be a PyG Data object
        data = data.to(self.device)
        out = self.model(data.x, data.edge_index)
        
        # Only train on nodes with known labels (class 1 and 2)
        # In Elliptic dataset, class 3 is unknown
        mask = (data.y == 0) | (data.y == 1) # Assuming labels mapped to 0, 1
        labeled_count = int(mask.sum().item())
        total_loss = None

        if labeled_count > 0:
            class_weights = self._compute_class_weights(data.y[mask], num_classes=out.shape[1])
            base_loss = F.nll_loss(out[mask], data.y[mask], weight=class_weights)
            total_loss = base_loss
            self.last_base_loss = float(base_loss.item())
        else:
            self.last_base_loss = 0.0

        pseudo_label_loss, pseudo_labeled_samples = self._pseudo_label_loss(out, data)
        self.last_pseudo_labeled_samples = int(pseudo_labeled_samples)
        if pseudo_label_loss is not None:
            total_loss = pseudo_label_loss if total_loss is None else total_loss + pseudo_label_loss
            self.last_pseudo_label_loss = float(pseudo_label_loss.item())
        else:
            self.last_pseudo_label_loss = 0.0

        proximal_penalty = self._fedprox_penalty()
        if proximal_penalty is not None:
            total_loss = proximal_penalty if total_loss is None else total_loss + proximal_penalty
            self.last_proximal_penalty = float(proximal_penalty.item())
        else:
            self.last_proximal_penalty = 0.0

        if total_loss is None:
            logger.warning("Skipping optimizer step because no labeled or confident pseudo-labeled samples were available")
            return 0.0

        total_loss.backward()
        self.optimizer.step()
        return total_loss.item()

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
            "pseudo_labeled_samples": float(self.last_pseudo_labeled_samples),
            "pseudo_label_loss": float(self.last_pseudo_label_loss),
            "sparse_label_mode": 1.0 if self.sparse_label_mode else 0.0,
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
        loaded_state = torch.load(buffer, map_location=self.device)
        current_state = self.model.state_dict()
        compatible_state = {}

        for name, value in loaded_state.items():
            current_value = current_state.get(name)
            if current_value is None:
                continue
            if tuple(value.shape) != tuple(current_value.shape):
                logger.warning(
                    "Skipping incompatible global weight tensor %s with shape %s; expected %s",
                    name,
                    tuple(value.shape),
                    tuple(current_value.shape),
                )
                continue
            compatible_state[name] = value

        if not compatible_state:
            logger.warning("No compatible global model weights found for the current local GNN schema")
            return

        self.model.load_state_dict(compatible_state, strict=False)
