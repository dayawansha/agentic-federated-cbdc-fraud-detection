import base64
import hashlib
import io
import importlib
import pickle
import sys
import types
import unittest

SERVICE_SRC = "/Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/central-coordinator/federated-model-aggregator/src"
if SERVICE_SRC not in sys.path:
    sys.path.insert(0, SERVICE_SRC)


def _install_fake_torch():
    fake_torch = types.ModuleType("torch")

    class FakeTensor:
        def __init__(self, value):
            self.value = float(value)

        def float(self):
            return self

        def item(self):
            return self.value

        def __add__(self, other):
            return FakeTensor(self.value + other.value)

        def __iadd__(self, other):
            self.value += other.value
            return self

        def __sub__(self, other):
            return FakeTensor(self.value - other.value)

        def __mul__(self, scalar):
            return FakeTensor(self.value * float(scalar))

        __rmul__ = __mul__

        def abs(self):
            return FakeTensor(abs(self.value))

        def mean(self):
            return self

    def save(obj, buffer):
        payload = {
            key: value.value if isinstance(value, FakeTensor) else float(value)
            for key, value in obj.items()
        }
        pickle.dump(payload, buffer)

    def load(buffer):
        payload = pickle.load(buffer)
        return {key: FakeTensor(value) for key, value in payload.items()}

    def zeros_like(value):
        return FakeTensor(0.0)

    def is_floating_point(_value):
        return True

    def randn_like(_value):
        return FakeTensor(0.0)

    fake_torch.FakeTensor = FakeTensor
    fake_torch.save = save
    fake_torch.load = load
    fake_torch.zeros_like = zeros_like
    fake_torch.is_floating_point = is_floating_point
    fake_torch.randn_like = randn_like
    fake_torch.Tensor = FakeTensor
    sys.modules["torch"] = fake_torch


try:
    import torch  # type: ignore
except ModuleNotFoundError:
    _install_fake_torch()
    import torch  # type: ignore

main = importlib.import_module("main")


def serialize_state(state_dict):
    buffer = io.BytesIO()
    torch.save(state_dict, buffer)
    return buffer.getvalue()


def deserialize_state(payload):
    return torch.load(io.BytesIO(payload))


def scalar_tensor(value):
    if hasattr(torch, "tensor"):
        try:
            return torch.tensor(value)
        except Exception:
            pass
    return torch.Tensor(value)


def scalar_value(value):
    if hasattr(value, "item"):
        try:
            return float(value.item())
        except Exception:
            pass
    if hasattr(value, "value"):
        return float(value.value)
    return float(value)


class TestFederatedModelAggregator(unittest.IsolatedAsyncioTestCase):
    async def test_federated_averaging_weights_by_sample_size(self):
        update_a = serialize_state({"weight": scalar_tensor(2.0)})
        update_b = serialize_state({"weight": scalar_tensor(4.0)})

        result = main.FederatedModelAggregator.federated_averaging([update_a, update_b], [1, 3])
        state = deserialize_state(result)

        self.assertAlmostEqual(scalar_value(state["weight"]), 3.5)

    async def test_aggregate_rejects_empty_updates(self):
        request = main.AggregateRequest(round_id="round-1", updates=[])

        with self.assertRaises(main.HTTPException) as exc:
            await main.aggregate(request)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "No updates provided")

    async def test_aggregate_returns_weighted_metrics(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(5.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-2",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=1,
                    metrics={"loss": 0.8},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=3,
                    metrics={"loss": 0.2},
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertAlmostEqual(response.global_metrics["loss"], 0.35)
        self.assertAlmostEqual(scalar_value(state["weight"]), 4.0)

    async def test_aggregate_supports_weighted_fedavg_with_reliability_scores(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(5.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-weighted",
            strategy="WeightedFedAvg",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=1,
                    reliability_score=0.2,
                    metrics={"loss": 0.9},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=1,
                    reliability_score=1.0,
                    metrics={"loss": 0.1},
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertGreater(scalar_value(state["weight"]), 4.0)
        self.assertLess(response.global_metrics["loss"], 0.3)

    async def test_aggregate_supports_performance_weighted_fedavg(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(5.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-performance",
            strategy="PerformanceWeightedFedAvg",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=1,
                    reliability_score=1.0,
                    metrics={"accuracy": 0.45, "f1_score": 0.40, "loss": 1.1},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=1,
                    reliability_score=1.0,
                    metrics={"accuracy": 0.95, "f1_score": 0.93, "loss": 0.1},
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertGreater(scalar_value(state["weight"]), 3.7)
        self.assertLess(response.global_metrics["loss"], 0.45)

    async def test_aggregate_supports_adaptive_fedavg_with_reliability_and_quality_weights(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(5.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-adaptive",
            strategy="AdaptiveFedAvg",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=2,
                    reliability_score=0.2,
                    metrics={"accuracy": 0.50, "f1_score": 0.48, "loss": 0.9},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=1,
                    reliability_score=1.0,
                    metrics={"accuracy": 0.96, "f1_score": 0.95, "loss": 0.05},
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertGreater(scalar_value(state["weight"]), 4.0)
        self.assertLess(response.global_metrics["loss"], 0.4)

    async def test_aggregate_supports_fedprox_gnn_with_reference_model_penalty(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(3.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(9.0)})).decode("ascii")
        reference = base64.b64encode(serialize_state({"weight": scalar_tensor(3.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-fedprox",
            strategy="FedProxGNN",
            global_reference_weights=reference,
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=1,
                    reliability_score=1.0,
                    metrics={"accuracy": 0.90, "f1_score": 0.88, "loss": 0.1},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=1,
                    reliability_score=1.0,
                    metrics={"accuracy": 0.90, "f1_score": 0.88, "loss": 0.1},
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertLess(scalar_value(state["weight"]), 6.0)
        self.assertGreaterEqual(scalar_value(state["weight"]), 3.0)

    async def test_aggregate_supports_fedgraph_with_graph_quality_weighting(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(2.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(8.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-fedgraph",
            strategy="FedGraph",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=1,
                    reliability_score=0.8,
                    metrics={
                        "accuracy": 0.85,
                        "f1_score": 0.83,
                        "graph_node_count": 50.0,
                        "graph_edge_count": 120.0,
                        "avg_degree": 2.4,
                        "graph_density": 0.02,
                        "labeled_ratio": 0.20,
                    },
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=1,
                    reliability_score=0.8,
                    metrics={
                        "accuracy": 0.85,
                        "f1_score": 0.83,
                        "graph_node_count": 250.0,
                        "graph_edge_count": 2200.0,
                        "avg_degree": 8.8,
                        "graph_density": 0.07,
                        "labeled_ratio": 0.92,
                    },
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertGreater(scalar_value(state["weight"]), 5.0)

    async def test_aggregate_supports_robust_median_strategy(self):
        request = main.AggregateRequest(
            round_id="round-robust",
            strategy="RobustMedian",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii"),
                    sample_size=1,
                    metrics={"loss": 0.2},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=base64.b64encode(serialize_state({"weight": scalar_tensor(2.0)})).decode("ascii"),
                    sample_size=1,
                    metrics={"loss": 0.2},
                    privacy_applied=True,
                ),
                main.AggregationItem(
                    agent_id="agent-c",
                    weights=base64.b64encode(serialize_state({"weight": scalar_tensor(100.0)})).decode("ascii"),
                    sample_size=1,
                    metrics={"loss": 0.2},
                    privacy_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertAlmostEqual(scalar_value(state["weight"]), 2.0)

    async def test_aggregate_decrypts_encrypted_payloads_when_present(self):
        raw_update = serialize_state({"weight": scalar_tensor(3.0)})
        encrypted_update = main.TRANSPORT_CIPHER.encrypt(raw_update)
        protected_hash = hashlib.sha256(base64.b64encode(raw_update).decode("ascii").encode("ascii")).hexdigest()
        encrypted_hash = hashlib.sha256(base64.b64encode(encrypted_update).decode("ascii").encode("ascii")).hexdigest()
        request = main.AggregateRequest(
            round_id="round-enc",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=base64.b64encode(raw_update).decode("ascii"),
                    encrypted_weights=base64.b64encode(encrypted_update).decode("ascii"),
                    protected_payload_sha256=protected_hash,
                    encrypted_payload_sha256=encrypted_hash,
                    sample_size=2,
                    metrics={"loss": 0.5},
                    privacy_applied=True,
                    encryption_applied=True,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertAlmostEqual(scalar_value(state["weight"]), 3.0)

    async def test_aggregate_rejects_payload_commitment_mismatch(self):
        raw_update = serialize_state({"weight": scalar_tensor(3.0)})
        encrypted_update = main.TRANSPORT_CIPHER.encrypt(raw_update)
        request = main.AggregateRequest(
            round_id="round-bad-hash",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=base64.b64encode(raw_update).decode("ascii"),
                    encrypted_weights=base64.b64encode(encrypted_update).decode("ascii"),
                    protected_payload_sha256="0" * 64,
                    encrypted_payload_sha256=hashlib.sha256(base64.b64encode(encrypted_update).decode("ascii").encode("ascii")).hexdigest(),
                    sample_size=2,
                    metrics={"loss": 0.5},
                    privacy_applied=True,
                    encryption_applied=True,
                ),
            ],
        )

        with self.assertRaises(main.HTTPException) as exc:
            await main.aggregate(request)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Protected commitment mismatch for agent-a")

    async def test_aggregate_rejects_unprotected_updates(self):
        raw_update = base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-unprotected",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=raw_update,
                    sample_size=1,
                    metrics={},
                    privacy_applied=False,
                ),
            ],
        )

        with self.assertRaises(main.HTTPException) as exc:
            await main.aggregate(request)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Update from agent-a is missing privacy protection")

    async def test_aggregate_uses_negotiated_weights(self):
        update_a = base64.b64encode(serialize_state({"weight": scalar_tensor(1.0)})).decode("ascii")
        update_b = base64.b64encode(serialize_state({"weight": scalar_tensor(5.0)})).decode("ascii")
        request = main.AggregateRequest(
            round_id="round-negotiated-test",
            updates=[
                main.AggregationItem(
                    agent_id="agent-a",
                    weights=update_a,
                    sample_size=1,
                    metrics={"loss": 0.8},
                    privacy_applied=True,
                    negotiated_weight=0.2,
                ),
                main.AggregationItem(
                    agent_id="agent-b",
                    weights=update_b,
                    sample_size=3,
                    metrics={"loss": 0.2},
                    privacy_applied=True,
                    negotiated_weight=0.8,
                ),
            ],
        )

        response = await main.aggregate(request)
        state = deserialize_state(base64.b64decode(response.aggregated_weights))

        self.assertTrue(response.success)
        self.assertAlmostEqual(scalar_value(state["weight"]), 4.2, places=5)
        self.assertAlmostEqual(response.global_metrics["loss"], 0.32)


if __name__ == "__main__":
    unittest.main()
