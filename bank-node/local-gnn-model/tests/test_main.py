import base64
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SRC = SERVICE_ROOT / "src"

if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))


class FakeValue:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class FakeVector:
    def __init__(self, values):
        self.values = [FakeValue(value) for value in values]

    def __getitem__(self, index):
        return self.values[index]


class FakePredictionList:
    def __init__(self, values):
        self.values = [FakeValue(value) for value in values]

    def __getitem__(self, index):
        return self.values[index]


class FakeLabelArray:
    def __init__(self, values):
        self.values = list(values)

    def cpu(self):
        return self

    def tolist(self):
        return list(self.values)


class FakeDataObject:
    def __init__(self):
        self.tx_ids = [11, 22, 33]
        self.y = FakeLabelArray([1, 0, 2])
        self.x = types.SimpleNamespace(shape=(3, 12))
        self.live_graph_used = False
        self.data_source = "static"
        self.sparse_label_mode = False
        self.unlabeled_count = 1
        self.exported_feature_count = 12


class FakeTrainer:
    def __init__(self):
        self.set_weights_calls = []
        self.configure_calls = []
        self.capture_calls = 0
        self.clear_calls = 0
        self.last_base_loss = 0.33
        self.last_proximal_penalty = 0.09
        self.use_label_propagation = False

    def set_model_weights(self, payload):
        self.set_weights_calls.append(payload)

    def configure_training(
        self,
        strategy="FedAvg",
        fedprox_mu=0.0,
        sparse_label_mode=False,
        pseudo_label_weight=0.0,
        pseudo_label_confidence=0.9,
        use_label_propagation=False,
    ):
        self.use_label_propagation = use_label_propagation
        self.configure_calls.append(
            {
                "strategy": strategy,
                "fedprox_mu": fedprox_mu,
                "sparse_label_mode": sparse_label_mode,
                "pseudo_label_weight": pseudo_label_weight,
                "pseudo_label_confidence": pseudo_label_confidence,
            }
        )

    def capture_proximal_reference(self):
        self.capture_calls += 1

    def clear_proximal_reference(self):
        self.clear_calls += 1

    def run_label_propagation(self, _data):
        return 0

    def train_epoch(self, _data):
        return 0.42

    def evaluate(self, _data):
        return {
            "accuracy": 0.88,
            "precision": 0.84,
            "recall": 0.81,
            "f1_score": 0.825,
            "roc_auc": 0.91,
            "labeled_samples": 2.0,
        }

    def get_model_weights(self):
        return b"trained-weights"

    def predict(self, _data):
        return {
            "predictions": FakePredictionList([1, 0, 2]),
            "probabilities": [
                FakeVector([0.01, 0.98, 0.01]),
                FakeVector([0.72, 0.20, 0.08]),
                FakeVector([0.20, 0.15, 0.65]),
            ],
        }


def _install_stub_modules():
    fake_torch = types.ModuleType("torch")
    fake_torch.Tensor = object
    sys.modules.setdefault("torch", fake_torch)
    sys.modules.setdefault("numpy", types.ModuleType("numpy"))
    sys.modules.setdefault("pandas", types.ModuleType("pandas"))

    pyg_data = types.ModuleType("torch_geometric.data")

    class Data:  # type: ignore
        pass

    pyg_data.Data = Data
    torch_geometric = types.ModuleType("torch_geometric")
    torch_geometric.data = pyg_data
    sys.modules.setdefault("torch_geometric", torch_geometric)
    sys.modules.setdefault("torch_geometric.data", pyg_data)

    src_model = types.ModuleType("src.model")
    src_model.get_model = lambda *args, **kwargs: object()
    src_trainer = types.ModuleType("src.trainer")

    class LocalTrainer:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

    src_trainer.LocalTrainer = LocalTrainer
    sys.modules.setdefault("src.model", src_model)
    sys.modules.setdefault("src.trainer", src_trainer)


_install_stub_modules()
main = importlib.import_module("main")


class TestLocalGnnModel(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        main._init_trainer.cache_clear()

    async def test_trigger_training_returns_metrics_and_sample_size(self):
        trainer = FakeTrainer()
        data = types.SimpleNamespace(y=types.SimpleNamespace(__eq__=None), x=types.SimpleNamespace(shape=(3, 12)))
        data.live_graph_used = False
        data.data_source = "static"
        data.sparse_label_mode = False
        data.unlabeled_count = 1
        data.exported_feature_count = 12

        class FakeMask:
            def __or__(self, _other):
                return self

            def sum(self):
                return FakeValue(2)

        class FakeLabels:
            def __eq__(self, other):
                return FakeMask()

            def __or__(self, other):
                return FakeMask()

        data.y = FakeLabels()

        encoded = base64.b64encode(b"global").decode("ascii")
        with patch.object(main, "_init_trainer", return_value=trainer), patch.object(main, "_load_graph_data", return_value=data):
            response = await main.trigger_training(main.TrainRequest(global_weights=encoded, epochs=2))

        self.assertEqual(response.status, "training_completed")
        self.assertEqual(response.sample_size, 2)
        self.assertEqual(response.metrics["accuracy"], 0.88)
        self.assertEqual(response.metrics["precision"], 0.84)
        self.assertEqual(response.metrics["recall"], 0.81)
        self.assertEqual(response.metrics["f1_score"], 0.825)
        self.assertEqual(response.metrics["roc_auc"], 0.91)
        self.assertEqual(response.metrics["loss"], 0.42)
        self.assertEqual(response.metrics["graph_node_count"], 3.0)
        self.assertEqual(response.metrics["graph_edge_count"], 0.0)
        self.assertEqual(response.metrics["avg_degree"], 0.0)
        self.assertEqual(response.metrics["graph_density"], 0.0)
        self.assertAlmostEqual(response.metrics["labeled_ratio"], 2.0 / 3.0)
        self.assertEqual(response.metrics["live_graph_used"], 0.0)
        self.assertEqual(response.metrics["data_source_live"], 0.0)
        self.assertEqual(response.metrics["sparse_label_mode"], 0.0)
        self.assertEqual(response.metrics["unlabeled_samples"], 1.0)
        self.assertEqual(response.metrics["pseudo_label_weight"], 0.35)
        self.assertEqual(response.metrics["pseudo_label_confidence"], 0.9)
        self.assertEqual(base64.b64decode(response.weights), b"trained-weights")
        self.assertEqual(trainer.set_weights_calls, [b"global"])
        self.assertEqual(
            trainer.configure_calls,
            [
                {
                    "strategy": "FedAvg",
                    "fedprox_mu": 1.0,
                    "sparse_label_mode": False,
                    "pseudo_label_weight": 0.35,
                    "pseudo_label_confidence": 0.9,
                }
            ],
        )
        self.assertEqual(trainer.clear_calls, 1)
        self.assertEqual(trainer.capture_calls, 0)

    async def test_trigger_training_configures_true_fedprox_round(self):
        trainer = FakeTrainer()
        data = types.SimpleNamespace(
            y=types.SimpleNamespace(__eq__=None),
            x=types.SimpleNamespace(shape=(3, 12)),
            edge_index=types.SimpleNamespace(shape=(2, 4)),
        )
        data.live_graph_used = True
        data.data_source = "live"
        data.sparse_label_mode = True
        data.unlabeled_count = 1
        data.exported_feature_count = 16

        class FakeMask:
            def __or__(self, _other):
                return self

            def sum(self):
                return FakeValue(2)

        class FakeLabels:
            def __eq__(self, other):
                return FakeMask()

            def __or__(self, other):
                return FakeMask()

        data.y = FakeLabels()

        encoded = base64.b64encode(b"global").decode("ascii")
        with patch.object(main, "_init_trainer", return_value=trainer), patch.object(main, "_load_graph_data", return_value=data):
            response = await main.trigger_training(
                main.TrainRequest(
                    global_weights=encoded,
                    epochs=1,
                    strategy="FedProxGNN",
                    fedprox_mu=0.75,
                    pseudo_label_weight=0.45,
                    pseudo_label_confidence=0.82,
                )
            )

        self.assertEqual(
            trainer.configure_calls,
            [
                {
                    "strategy": "FedProxGNN",
                    "fedprox_mu": 0.75,
                    "sparse_label_mode": True,
                    "pseudo_label_weight": 0.45,
                    "pseudo_label_confidence": 0.82,
                }
            ],
        )
        self.assertEqual(trainer.capture_calls, 1)
        self.assertEqual(trainer.clear_calls, 0)
        self.assertEqual(response.metrics["fedprox_mu"], 0.75)
        self.assertEqual(response.metrics["fedprox_base_loss"], 0.33)
        self.assertEqual(response.metrics["fedprox_penalty"], 0.09)
        self.assertEqual(response.metrics["live_graph_used"], 1.0)
        self.assertEqual(response.metrics["data_source_live"], 1.0)
        self.assertEqual(response.metrics["sparse_label_mode"], 1.0)
        self.assertEqual(response.metrics["pseudo_label_weight"], 0.45)
        self.assertEqual(response.metrics["pseudo_label_confidence"], 0.82)

    async def test_run_inference_ranks_predictions_when_tx_ids_not_provided(self):
        trainer = FakeTrainer()
        data = FakeDataObject()

        with patch.object(main, "_init_trainer", return_value=trainer), patch.object(main, "_load_graph_data", return_value=data):
            response = await main.run_inference(main.InferenceRequest(limit=2))

        self.assertEqual(response.status, "inference_completed")
        self.assertEqual(response.prediction_count, 2)
        self.assertEqual([item.tx_id for item in response.predictions], [11, 22])
        self.assertEqual(response.predictions[0].predicted_class, "illicit")

    async def test_run_inference_raises_404_for_missing_tx_id(self):
        trainer = FakeTrainer()
        data = FakeDataObject()

        with patch.object(main, "_init_trainer", return_value=trainer), patch.object(main, "_load_graph_data", return_value=data):
            with self.assertRaises(main.HTTPException) as exc:
                await main.run_inference(main.InferenceRequest(tx_ids=[99], limit=5))

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, {"missing_tx_ids": [99]})

    async def test_init_trainer_uses_hybrid_model_configuration_by_default(self):
        data = types.SimpleNamespace(x=types.SimpleNamespace(shape=(3, 12)))

        with patch.object(main, "_load_graph_data", return_value=data), patch.object(main, "get_model", return_value=object()) as get_model_mock, patch.object(main, "LocalTrainer") as trainer_cls, patch.dict(
            os.environ,
            {
                "MODEL_TYPE": "HYBRID",
                "MODEL_HEADS": "6",
                "MODEL_DROPOUT": "0.25",
                "HIDDEN_DIM": "96",
                "OUTPUT_DIM": "3",
            },
            clear=False,
        ):
            main._init_trainer.cache_clear()
            main._init_trainer(data.x.shape[1])

        get_model_mock.assert_called_once_with(
            input_dim=12,
            hidden_dim=96,
            output_dim=3,
            model_type="HYBRID",
            num_heads=6,
            dropout=0.25,
        )
        trainer_cls.assert_called_once()

    def test_extract_numeric_transaction_id_accepts_prefixed_transaction_ids(self):
        self.assertEqual(main._extract_numeric_transaction_id("tx-42"), 42)
        self.assertEqual(main._extract_numeric_transaction_id("transaction_0007"), 7)


if __name__ == "__main__":
    unittest.main()
