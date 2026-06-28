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
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(2, 2, bias=False)

    def forward(self, x, _edge_index):
        return F.log_softmax(self.linear(x), dim=1)


class FakeData:
    def __init__(self, x, y, edge_index):
        self.x = x
        self.y = y
        self.edge_index = edge_index

    def to(self, _device):
        return self


class TestLocalTrainerFedProx(unittest.TestCase):
    def test_train_epoch_adds_fedprox_penalty_against_captured_reference(self):
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


if __name__ == "__main__":
    unittest.main()
