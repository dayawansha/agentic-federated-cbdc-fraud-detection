import importlib
import sys
import unittest
from pathlib import Path

if "torch" in sys.modules and not hasattr(sys.modules["torch"], "nn"):
    del sys.modules["torch"]

torch = importlib.import_module("torch")
nn = importlib.import_module("torch.nn")
F = importlib.import_module("torch.nn.functional")

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SRC = SERVICE_ROOT / "src"

if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

from trainer import LocalTrainer


class SimpleGraphModel(nn.Module):
    """A minimal single-layer stand-in for FraudGNN, used to keep trainer tests fast and deterministic."""
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(2, 2, bias=False)

    def forward(self, x, _edge_index):
        """Ignores graph structure entirely and just classifies node features linearly."""
        return F.log_softmax(self.linear(x), dim=1)


class FakeData:
    """Lightweight stand-in for a PyTorch Geometric `Data` object, holding just what LocalTrainer needs."""
    def __init__(self, x, y, edge_index):
        self.x = x
        self.y = y
        self.edge_index = edge_index

    def to(self, _device):
        """No-op device transfer (tests run on CPU only), mirrors the real Data.to() API."""
        return self


class TestLocalTrainerFedProx(unittest.TestCase):
    def test_train_epoch_adds_fedprox_penalty_against_captured_reference(self):
        """Verifies FedProx mode adds a positive proximal penalty once local weights drift from the captured global reference."""
        torch.manual_seed(7)
        model = SimpleGraphModel()
        trainer = LocalTrainer(model=model, lr=0.0, weight_decay=0.0)
        trainer.configure_training(strategy="FedProxGNN", fedprox_mu=0.5)
        trainer.capture_proximal_reference()

        with torch.no_grad():
            trainer.model.linear.weight.add_(1.0)

        data = FakeData(
            x=torch.tensor([[1.0, 0.0], [0.0, 1.0]], dtype=torch.float32),
            y=torch.tensor([0, 1], dtype=torch.long),
            edge_index=torch.tensor([[0, 1], [1, 0]], dtype=torch.long),
        )

        total_loss = trainer.train_epoch(data)

        self.assertGreater(trainer.last_proximal_penalty, 0.0)
        self.assertGreater(total_loss, trainer.last_base_loss)

    def test_train_epoch_uses_confident_pseudo_labels_in_sparse_mode(self):
        """Verifies that in sparse-label mode, high-confidence pseudo-labels on unlabeled nodes contribute a positive loss term."""
        torch.manual_seed(11)
        model = SimpleGraphModel()
        trainer = LocalTrainer(model=model, lr=0.0, weight_decay=0.0)
        trainer.configure_training(
            strategy="FedAvg",
            fedprox_mu=0.0,
            sparse_label_mode=True,
            pseudo_label_weight=0.4,
            pseudo_label_confidence=0.6,
        )

        with torch.no_grad():
            trainer.model.linear.weight.copy_(torch.tensor([[2.0, -1.0], [-2.0, 1.0]], dtype=torch.float32))

        data = FakeData(
            x=torch.tensor([[1.0, 0.0], [1.2, 0.1]], dtype=torch.float32),
            y=torch.tensor([2, 2], dtype=torch.long),
            edge_index=torch.tensor([[0, 1], [1, 0]], dtype=torch.long),
        )

        total_loss = trainer.train_epoch(data)

        self.assertGreater(total_loss, 0.0)
        self.assertGreater(trainer.last_pseudo_label_loss, 0.0)
        self.assertGreater(trainer.last_pseudo_labeled_samples, 0)

    def test_label_propagation_updates_unknown_labels(self):
        """Verifies label propagation assigns a confident label to an unknown node connected to a known-labeled neighbor."""
        model = SimpleGraphModel()
        trainer = LocalTrainer(model=model)
        trainer.configure_training(use_label_propagation=True)

        # Node 0 has label 1, Node 1 is unlabeled (2)
        # Node 0 is connected to Node 1
        data = FakeData(
            x=torch.tensor([[1.0, 0.0], [0.0, 1.0]], dtype=torch.float32),
            y=torch.tensor([1, 2], dtype=torch.long),
            edge_index=torch.tensor([[0, 1], [1, 0]], dtype=torch.long),
        )

        newly_labeled = trainer.run_label_propagation(data, alpha=0.9, iterations=10, threshold=0.1)

        self.assertEqual(newly_labeled, 1)
        self.assertEqual(int(data.y[1].item()), 1)


if __name__ == "__main__":
    unittest.main()
