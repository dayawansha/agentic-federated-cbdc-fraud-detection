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
# Import PyTorch (a popular open-source machine learning framework for Python)
import torch
# Import neural network functions (like loss calculators)
import torch.nn.functional as F
# Import the logging library to output text messages to console
import logging

# Set up logging so we can see printouts in our terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalTrainer:
    """
    This class handles the actual training process of a local GNN (Graph Neural Network)
    on a bank's local transaction database.
    """
    def __init__(self, model, lr=0.01, weight_decay=5e-4):
        # 'self.model' is the GNN neural network model itself
        self.model = model
        
        # 'self.optimizer' is the mathematical optimizer (Adam) that adjusts the model's numbers (weights)
        # to decrease the error rate (loss). 'lr' is learning rate (size of steps it takes).
        self.optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        
        # Determine whether to run calculations on a graphics card (GPU/cuda) or standard processor (CPU)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Move the neural network to the chosen device (GPU or CPU)
        self.model.to(self.device)
        
        # Default strategy is "FedAvg" (standard model averaging)
        self.training_strategy = "FedAvg"
        # regularization parameter for FedProx
        self.fedprox_mu = 0.0
        # Reference weights of the global model (downloaded from central registry)
        self.global_reference_params = None
        # Flag indicating whether we have very few labels (sparse labels)
        self.sparse_label_mode = False
        # Flag indicating if we want to run Label Propagation before training
        self.use_label_propagation = False
        # Weight/importance of self-guessed (pseudo-labels) nodes in our loss calculation
        self.pseudo_label_weight = 0.0
        # The probability threshold (e.g., 90%) required to trust a guess
        self.pseudo_label_confidence = 0.9
        
        # Track historical metrics for reporting
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
        use_label_propagation: bool = False,
    ):
        """
        Configures the learning behavior prior to executing a round's training.
        """
        # Save training strategy name (standardized to text string)
        self.training_strategy = str(strategy or "FedAvg")
        # Ensure FedProx regularization constant is not negative
        self.fedprox_mu = max(0.0, float(fedprox_mu or 0.0))
        # Save boolean flag (True or False) for sparse label mode
        self.sparse_label_mode = bool(sparse_label_mode)
        # Ensure pseudo label weight is >= 0
        self.pseudo_label_weight = max(0.0, float(pseudo_label_weight or 0.0))
        # Ensure pseudo label confidence is between 0.5 (50%) and 0.999 (99.9%)
        self.pseudo_label_confidence = min(0.999, max(0.5, float(pseudo_label_confidence or 0.9)))
        # Save label propagation toggle flag
        self.use_label_propagation = bool(use_label_propagation)
        
        # Reset counters for the current round
        self.last_base_loss = 0.0
        self.last_proximal_penalty = 0.0
        self.last_pseudo_label_loss = 0.0
        self.last_pseudo_labeled_samples = 0
        
        # If we are not using the FedProx strategy, discard global references to save RAM
        if self.training_strategy != "FedProxGNN":
            self.global_reference_params = None

    def run_label_propagation(self, data, alpha: float = 0.85, iterations: int = 15, threshold: float = 0.8) -> int:
        """
        Label Propagation algorithm to resolve sparse or delayed labels.
        
        For non-Python/non-ML readers:
        - If a bank has 10,000 transactions but only 100 are explicitly checked/labeled as:
          - Class 0 (Licit / clean transactions)
          - Class 1 (Illicit / fraudulent transactions)
          - Class 2 (Unknown)
        - This algorithm behaves like gossip: a node tells its neighbors what label it is.
        - Over several iterations, the clean/fraud labels flow along connections to fill in the "unknown" gaps.
        - If we are very confident (prob >= 80%) about a guess, we assign that label permanently for training.
        """
        # Find the number of transactions (nodes) in the graph dataset
        num_nodes = data.x.size(0)
        # If there are no nodes or no edges connecting them, we cannot propagate labels
        if num_nodes == 0 or data.edge_index.size(1) == 0:
            return 0

        # Initialize a grid of probabilities (Y matrix) of shape [num_nodes, 3] with all zeros
        # There are 3 classes: index 0 (licit), index 1 (illicit), index 2 (unknown)
        Y = torch.zeros((num_nodes, 3), device=self.device)
        
        # Create masks (true/false filters) to separate known labeled nodes from unknown ones
        known_mask = (data.y == 0) | (data.y == 1)
        unknown_mask = ~known_mask
        
        # Assign 1.0 (100% probability) for known nodes to their correct class index (0 or 1)
        Y[known_mask, data.y[known_mask]] = 1.0
        # Assign 1.0 probability for unknown nodes to class index 2 (unknown)
        Y[unknown_mask, 2] = 1.0
        
        # Store a copy of the initial state so we can mix it back during iterations
        Y_init = Y.clone()
        
        # Get the edge connections: 'src' is the sender transactions, 'dst' is the receiver transactions
        edge_index = data.edge_index.to(self.device)
        src, dst = edge_index[0], edge_index[1]
        
        # Count the number of connections (degree) for each transaction node
        deg = torch.bincount(src, minlength=num_nodes).float()
        # Scale factor (inverse square root) so nodes with thousands of connections don't overpower others
        deg_inv_sqrt = deg.pow(-0.5)
        # Clean up any division-by-zero infinite values
        deg_inv_sqrt[torch.isinf(deg_inv_sqrt)] = 0.0
        
        # Run the propagation loop (default: 15 times)
        for _ in range(iterations):
            # Scale probability values by degree weights
            Y_scaled = Y * deg_inv_sqrt.view(-1, 1)
            
            # Aggregate neighbors: Sum up the scaled probabilities of incoming connection senders into receiver slots
            Y_agg = torch.zeros_like(Y)
            Y_agg.index_add_(0, dst, Y_scaled[src])
            
            # Scale receiver probabilities
            Y_agg = Y_agg * deg_inv_sqrt.view(-1, 1)
            
            # Mix rule: new probability = 85% of neighbor gossip + 15% of initial label state
            Y = alpha * Y_agg + (1 - alpha) * Y_init
            
            # Clamp known nodes back to their 100% correct class (they are ground truth and should not change)
            Y[known_mask] = Y_init[known_mask]
            
        # Look at the final probabilities for the 'unknown' nodes, focusing only on classes 0 and 1
        probs_classes = Y[unknown_mask][:, :2]
        # Find the highest probability (confidence) and the index of that class (0 or 1)
        confidences, predicted_labels = probs_classes.max(dim=1)
        
        # Create a filter of nodes where our confidence meets or exceeds the threshold (e.g. 80%)
        confident_propagation_mask = confidences >= threshold
        newly_labeled_count = 0
        
        if confident_propagation_mask.any():
            # Find the actual indices of these unknown nodes
            unknown_indices = torch.nonzero(unknown_mask).squeeze(1)
            # Filter to find only the highly confident ones
            confident_unknown_indices = unknown_indices[confident_propagation_mask]
            predicted_labels_for_confident = predicted_labels[confident_propagation_mask]
            
            # Apply the propagated label (0 or 1) directly to the dataset labels
            data.y[confident_unknown_indices] = predicted_labels_for_confident
            # Count how many we labeled
            newly_labeled_count = int(confident_propagation_mask.sum().item())
            logger.info(f"Label Propagation: Autonomously assigned {newly_labeled_count} labels to unknown nodes.")
            
        return newly_labeled_count

    def capture_proximal_reference(self):
        """
        Saves a snapshot of the current model's weights.
        Used by FedProx to compare local weight drift against the global baseline.
        """
        self.global_reference_params = {
            name: parameter.detach().clone().to(self.device)
            for name, parameter in self.model.named_parameters()
            if parameter.requires_grad
        }

    def clear_proximal_reference(self):
        """
        Clears the stored global baseline weights from memory.
        """
        self.global_reference_params = None
        self.last_proximal_penalty = 0.0

    def _fedprox_penalty(self):
        """
        Calculates the proximal distance penalty for FedProx.
        """
        if self.training_strategy != "FedProxGNN" or self.fedprox_mu <= 0 or not self.global_reference_params:
            return None

        penalty = None
        # Loop through all learnable parts of our neural net
        for name, parameter in self.model.named_parameters():
            if not parameter.requires_grad:
                continue
            reference = self.global_reference_params.get(name)
            if reference is None:
                continue
            # Calculate squared distance between current local weights and the global reference weights
            distance = torch.sum((parameter - reference) ** 2)
            penalty = distance if penalty is None else penalty + distance
            
        if penalty is None:
            return None
        # Return scaled penalty: 0.5 * mu * sum(squared distances)
        return 0.5 * self.fedprox_mu * penalty

    def _pseudo_label_loss(self, log_probs, data):
        """
        Calculates the loss/error on self-predicted guesses for unlabeled nodes.
        """
        if not self.sparse_label_mode or self.pseudo_label_weight <= 0.0:
            return None, 0

        # Select nodes labeled as 2 (which represents unlabeled/unknown)
        unlabeled_mask = data.y == 2
        unlabeled_count = int(unlabeled_mask.sum().item())
        if unlabeled_count == 0:
            return None, 0

        # Calculate prediction probabilities for unlabeled nodes
        unlabeled_log_probs = log_probs[unlabeled_mask]
        unlabeled_probs = torch.exp(unlabeled_log_probs)
        # Find the model's guess and how confident it is (0.0 to 1.0)
        confidences, pseudo_labels = unlabeled_probs.max(dim=1)
        
        # Filter for guesses that meet our confidence threshold (e.g. 90%)
        confident_mask = confidences >= self.pseudo_label_confidence

        # If model outputs 3 classes, filter out any guesses that class is 2 (unknown)
        if unlabeled_probs.shape[1] > 2:
            confident_mask = confident_mask & (pseudo_labels != 2)

        confident_count = int(confident_mask.sum().item())
        if confident_count == 0:
            return None, 0

        # Calculate the error (negative log likelihood loss) of our confident guesses
        pseudo_loss = F.nll_loss(unlabeled_log_probs[confident_mask], pseudo_labels[confident_mask])
        # Scale the error by the pseudo-label weight constant
        return pseudo_loss * self.pseudo_label_weight, confident_count

    def train_epoch(self, data):
        """
        Runs one iteration (epoch) of local training on the dataset.
        """
        # Set the model to training mode
        self.model.train()
        # Reset the optimizer's gradients (clears math calculators from last step)
        self.optimizer.zero_grad()
        
        # Move our graph data to the GPU/CPU device
        data = data.to(self.device)
        # Run the graph neural network forward pass to get prediction probabilities
        out = self.model(data.x, data.edge_index)
        
        # Filter for nodes with known labels (0 = licit, 1 = illicit)
        mask = (data.y == 0) | (data.y == 1)
        labeled_count = int(mask.sum().item())
        total_loss = None

        if labeled_count > 0:
            # Compute class weights to handle imbalanced data (clean transactions are much more common than fraud)
            class_weights = self._compute_class_weights(data.y[mask], num_classes=out.shape[1])
            # Calculate classification loss/error on labeled data
            base_loss = F.nll_loss(out[mask], data.y[mask], weight=class_weights)
            total_loss = base_loss
            self.last_base_loss = float(base_loss.item())
        else:
            self.last_base_loss = 0.0

        # Calculate pseudo-label loss on unlabeled transactions (guiding learning via self-predictions)
        pseudo_label_loss, pseudo_labeled_samples = self._pseudo_label_loss(out, data)
        self.last_pseudo_labeled_samples = int(pseudo_labeled_samples)
        if pseudo_label_loss is not None:
            total_loss = pseudo_label_loss if total_loss is None else total_loss + pseudo_label_loss
            self.last_pseudo_label_loss = float(pseudo_label_loss.item())
        else:
            self.last_pseudo_label_loss = 0.0

        # Calculate FedProx regularization penalty (preventing weights from drifting too far from global model)
        proximal_penalty = self._fedprox_penalty()
        if proximal_penalty is not None:
            total_loss = proximal_penalty if total_loss is None else total_loss + proximal_penalty
            self.last_proximal_penalty = float(proximal_penalty.item())
        else:
            self.last_proximal_penalty = 0.0

        # If we have no learning signals, skip the optimization step
        if total_loss is None:
            logger.warning("Skipping optimizer step because no labeled or confident pseudo-labeled samples were available")
            return 0.0

        # Backpropagation: calculate the mathematical direction to adjust parameters to decrease error
        total_loss.backward()
        # Step: Let the optimizer adjust all model parameters in that direction
        self.optimizer.step()
        return total_loss.item()

    def evaluate(self, data):
        """
        Evaluates the current model on the local dataset and calculates metrics (accuracy, precision, recall, F1-score, ROC AUC).
        """
        # Set the model to evaluation/testing mode
        self.model.eval()
        data = data.to(self.device)
        
        # Disable gradient calculations to save CPU/RAM since we are only evaluating, not training
        with torch.no_grad():
            # Get prediction probabilities
            log_probs = self.model(data.x, data.edge_index)
            probs = torch.exp(log_probs)
            # Find highest probability index (0, 1, or 2)
            pred = probs.argmax(dim=1)

            # Filter for labeled validation nodes
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

            # Calculate True Positives, True Negatives, False Positives, and False Negatives
            tp = int(((y_pred == 1) & (y_true == 1)).sum().item()) # Correctly caught fraud
            tn = int(((y_pred == 0) & (y_true == 0)).sum().item()) # Correctly identified clean
            fp = int(((y_pred == 1) & (y_true == 0)).sum().item()) # Clean flagged as fraud (false alarm)
            fn = int(((y_pred == 0) & (y_true == 1)).sum().item()) # Fraud missed

            # Calculate final stats
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
        """
        Balances the loss calculation.
        If there are 100 licit nodes and 2 illicit nodes, illicit nodes are weighted 50x more
        so the model doesn't just learn to guess "clean" for everything.
        """
        label_tensor = labels.detach()
        # Count frequency of each class label
        counts = torch.bincount(label_tensor, minlength=num_classes).float()
        counts = torch.clamp(counts, min=1.0)
        # Compute inverse frequency weights
        weights = counts.sum() / (counts * counts.numel())
        return weights.to(self.device)

    @staticmethod
    def _binary_roc_auc_score(y_true, y_score):
        """
        Calculates ROC Area Under the Curve.
        Represents the probability that the GNN ranks a random fraud node higher than a random clean node.
        """
        positives = sum(1 for label in y_true if int(label) == 1)
        negatives = sum(1 for label in y_true if int(label) == 0)
        if positives == 0 or negatives == 0:
            return 0.0

        # Sort the pairs by score
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
        """
        Evaluates the model on data and returns prediction label and probabilities.
        """
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
        """
        Saves the neural net weights as binary bytes to be sent over networks.
        """
        import io
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        return buffer.getvalue()

    def set_model_weights(self, weights_bytes: bytes):
        """
        Loads GNN weights from raw binary bytes.
        """
        import io
        buffer = io.BytesIO(weights_bytes)
        # Load weight tensors
        loaded_state = torch.load(buffer, map_location=self.device)
        current_state = self.model.state_dict()
        compatible_state = {}

        # Validate that shapes match perfectly before loading
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

        # Load weights into the model structure
        self.model.load_state_dict(compatible_state, strict=False)
