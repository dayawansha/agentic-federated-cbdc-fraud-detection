import asyncio
import base64
import hashlib
import importlib
import json
import io
import os
import pickle
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

REPO_ROOT = Path("/Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection")
SERVICE_SRC = REPO_ROOT / "central-coordinator" / "policy-manager" / "src"

for path in (str(REPO_ROOT), str(SERVICE_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

TEMP_DIR = tempfile.mkdtemp(prefix="policy-manager-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEMP_DIR) / 'policy.db'}"

main = importlib.import_module("main")


def _install_fake_torch():
    fake_torch = types.ModuleType("torch")

    class FakeTensor:
        def __init__(self, value):
            self.value = float(value)

        def float(self):
            return self

        def __add__(self, other):
            return FakeTensor(self.value + other.value)

        def __iadd__(self, other):
            self.value += other.value
            return self

        def __mul__(self, scalar):
            return FakeTensor(self.value * float(scalar))

        __rmul__ = __mul__

    def save(obj, buffer):
        payload = {key: value.value for key, value in obj.items()}
        pickle.dump(payload, buffer)

    def load(buffer):
        payload = pickle.load(buffer)
        return {key: FakeTensor(value) for key, value in payload.items()}

    def zeros_like(_value):
        return FakeTensor(0.0)

    fake_torch.Tensor = FakeTensor
    fake_torch.save = save
    fake_torch.load = load
    fake_torch.zeros_like = zeros_like
    return fake_torch


def _serialize_mask(value: float) -> str:
    fake_torch = _install_fake_torch()
    buffer = io.BytesIO()
    fake_torch.save({"weight": fake_torch.Tensor(value)}, buffer)
    encrypted = main.TRANSPORT_CIPHER.encrypt(buffer.getvalue())
    return base64.b64encode(encrypted).decode("ascii")


def _serialize_escrow_mask(value: float, round_id: str, agent_id: str) -> str:
    fake_torch = _install_fake_torch()
    buffer = io.BytesIO()
    fake_torch.save({"weight": fake_torch.Tensor(value)}, buffer)
    payload = buffer.getvalue()

    ephemeral_private_key = x25519.X25519PrivateKey.generate()
    escrow_public_key = x25519.X25519PublicKey.from_public_bytes(main.ESCROW_PUBLIC_KEY)
    shared_secret = ephemeral_private_key.exchange(escrow_public_key)
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"secure-aggregation:{round_id}:{agent_id}".encode("utf-8"),
    ).derive(shared_secret)
    cipher = Fernet(base64.urlsafe_b64encode(derived_key))
    ciphertext = cipher.encrypt(payload)
    package = {
        "scheme": "x25519-hkdf-fernet-v1",
        "round_id": round_id,
        "agent_id": agent_id,
        "ephemeral_public_key": base64.b64encode(
            ephemeral_private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "mask_commitment": hashlib.sha256(payload).hexdigest(),
    }
    return json.dumps(package, separators=(",", ":"))


def _deserialize_mask(mask_b64: str):
    fake_torch = _install_fake_torch()
    return fake_torch.load(io.BytesIO(base64.b64decode(mask_b64)))


class TestPolicyManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(main.startup_event())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    def setUp(self):
        main.Base.metadata.drop_all(bind=main.engine)
        main.Base.metadata.create_all(bind=main.engine)

    def test_get_agent_budget_creates_default_budget(self):
        budget = asyncio.run(main.get_agent_budget("agent-a"))

        self.assertEqual(budget.epsilon, 10.0)
        self.assertEqual(budget.delta, 1e-5)
        self.assertEqual(budget.total_spent_epsilon, 0.0)
        self.assertEqual(budget.total_spent_delta, 0.0)

    def test_update_budget_accumulates_spend(self):
        response = asyncio.run(
            main.update_budget(
                main.BudgetUpdateRequest(
                    agent_id="agent-b",
                    epsilon_spent=0.4,
                    delta_spent=1e-6,
                )
            )
        )

        budget = response["current_budget"]
        self.assertEqual(response["status"], "success")
        self.assertAlmostEqual(budget.total_spent_epsilon, 0.4)
        self.assertAlmostEqual(budget.total_spent_delta, 1e-6)
        self.assertEqual(budget.epsilon, 10.0)

    def test_update_budget_rejects_exceeded_epsilon(self):
        asyncio.run(
            main.set_budget(
                main.BudgetSetRequest(
                    agent_id="agent-c",
                    epsilon=0.5,
                    delta=1e-5,
                )
            )
        )

        with self.assertRaises(main.HTTPException) as exc:
            asyncio.run(
                main.update_budget(
                    main.BudgetUpdateRequest(
                        agent_id="agent-c",
                        epsilon_spent=0.6,
                        delta_spent=0.0,
                    )
                )
            )

        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail, "Privacy budget exceeded (epsilon)")

    def test_get_global_policies_exposes_round_and_update_thresholds(self):
        policies = asyncio.run(main.get_global_policies())

        self.assertEqual(policies["min_agents_per_round"], 1)
        self.assertEqual(policies["aggregation_strategy"], "FedAvg")
        self.assertEqual(policies["fallback_aggregation_strategy"], "AdaptiveFedAvg")
        self.assertEqual(policies["adaptive_strategy_on_rejection"], "PerformanceWeightedFedAvg")
        self.assertEqual(policies["fedprox_mu"], 1.0)
        self.assertEqual(policies["required_metrics"], ["accuracy", "f1_score"])
        self.assertGreaterEqual(policies["min_update_accuracy"], 0.5)
        self.assertGreaterEqual(policies["min_update_sample_size"], 1)
        self.assertGreaterEqual(policies["max_accuracy_peer_delta"], 0.0)
        self.assertGreaterEqual(policies["max_loss_peer_delta"], 0.0)
        self.assertGreaterEqual(policies["max_noise_multiplier"], policies["min_noise_multiplier"])
        self.assertTrue(policies["require_encrypted_updates"])

    def test_update_global_policies_persists_versioned_governance_rules(self):
        updated = asyncio.run(
            main.update_global_policies(
                main.GlobalPolicyUpdateRequest(
                    policies={"minimum_agent_reliability_score": 0.75, "aggregation_strategy": "AdaptiveFedAvg"},
                    updated_by="tester",
                )
            )
        )

        self.assertEqual(updated["aggregation_strategy"], "AdaptiveFedAvg")
        self.assertEqual(updated["updated_by"], "tester")
        self.assertGreaterEqual(updated["policy_version"], 2)
        self.assertAlmostEqual(updated["minimum_agent_reliability_score"], 0.75)

    def test_exposes_secure_aggregation_escrow_public_key(self):
        response = asyncio.run(main.get_secure_aggregation_escrow_public_key())
        self.assertEqual(response.scheme, "x25519-hkdf-fernet-v1")
        self.assertTrue(response.public_key)

    def test_governance_agent_upsert_and_audit_log(self):
        agent = asyncio.run(
            main.upsert_governance_agent(
                main.GovernanceAgentRequest(
                    agent_id="agent-z",
                    active=False,
                    allowed_asset_types=["CBDC", "RTGS"],
                    minimum_reliability_score=0.6,
                    notes="temporarily quarantined",
                )
            )
        )

        audit_events = asyncio.run(main.list_governance_audit(limit=10))

        self.assertEqual(agent.agent_id, "agent-z")
        self.assertFalse(agent.active)
        self.assertEqual(agent.allowed_asset_types, ["CBDC", "RTGS"])
        self.assertAlmostEqual(agent.minimum_reliability_score, 0.6)
        self.assertTrue(any(event.agent_id == "agent-z" and event.event_type == "governance_agent_upserted" for event in audit_events))

    def test_secure_aggregation_masks_are_stored_and_aggregated_with_fake_torch(self):
        with patch.dict(sys.modules, {"torch": _install_fake_torch()}):
            asyncio.run(
                main.submit_secure_aggregation_mask(
                    main.SecureAggregationMaskSubmitRequest(
                        round_id="round-mask",
                        agent_id="agent-a",
                        encrypted_mask_share=_serialize_escrow_mask(2.0, "round-mask", "agent-a"),
                    )
                )
            )
            asyncio.run(
                main.submit_secure_aggregation_mask(
                    main.SecureAggregationMaskSubmitRequest(
                        round_id="round-mask",
                        agent_id="agent-b",
                        encrypted_mask_share=_serialize_escrow_mask(4.0, "round-mask", "agent-b"),
                    )
                )
            )
            response = asyncio.run(
                main.aggregate_secure_aggregation_masks(
                    main.SecureAggregationMaskAggregateRequest(
                        round_id="round-mask",
                        strategy="FedAvg",
                        updates=[
                            main.SecureAggregationMaskAggregateItem(agent_id="agent-a", sample_size=1, reliability_score=1.0),
                            main.SecureAggregationMaskAggregateItem(agent_id="agent-b", sample_size=3, reliability_score=1.0),
                        ],
                    )
                )
            )

        state = _deserialize_mask(response.aggregate_mask)
        self.assertEqual(response.participant_count, 2)
        self.assertAlmostEqual(state["weight"].value, 3.5)

    def test_secure_aggregation_masks_support_adaptive_weighting(self):
        with patch.dict(sys.modules, {"torch": _install_fake_torch()}):
            asyncio.run(
                main.submit_secure_aggregation_mask(
                    main.SecureAggregationMaskSubmitRequest(
                        round_id="round-mask-adaptive",
                        agent_id="agent-a",
                        encrypted_mask_share=_serialize_escrow_mask(1.0, "round-mask-adaptive", "agent-a"),
                    )
                )
            )
            asyncio.run(
                main.submit_secure_aggregation_mask(
                    main.SecureAggregationMaskSubmitRequest(
                        round_id="round-mask-adaptive",
                        agent_id="agent-b",
                        encrypted_mask_share=_serialize_escrow_mask(5.0, "round-mask-adaptive", "agent-b"),
                    )
                )
            )
            response = asyncio.run(
                main.aggregate_secure_aggregation_masks(
                    main.SecureAggregationMaskAggregateRequest(
                        round_id="round-mask-adaptive",
                        strategy="AdaptiveFedAvg",
                        updates=[
                            main.SecureAggregationMaskAggregateItem(
                                agent_id="agent-a",
                                sample_size=2,
                                reliability_score=0.2,
                                metrics={"accuracy": 0.5, "f1_score": 0.48, "loss": 0.9},
                            ),
                            main.SecureAggregationMaskAggregateItem(
                                agent_id="agent-b",
                                sample_size=1,
                                reliability_score=1.0,
                                metrics={"accuracy": 0.96, "f1_score": 0.95, "loss": 0.05},
                            ),
                        ],
                    )
                )
            )

        state = _deserialize_mask(response.aggregate_mask)
        self.assertEqual(response.participant_count, 2)
        self.assertGreater(state["weight"].value, 4.0)

    def test_secure_aggregation_masks_legacy_transport_format_still_supported(self):
        with patch.dict(sys.modules, {"torch": _install_fake_torch()}):
            asyncio.run(
                main.submit_secure_aggregation_mask(
                    main.SecureAggregationMaskSubmitRequest(
                        round_id="round-mask-legacy",
                        agent_id="agent-a",
                        encrypted_mask_share=_serialize_mask(1.0),
                    )
                )
            )
            response = asyncio.run(
                main.aggregate_secure_aggregation_masks(
                    main.SecureAggregationMaskAggregateRequest(
                        round_id="round-mask-legacy",
                        strategy="FedAvg",
                        updates=[
                            main.SecureAggregationMaskAggregateItem(agent_id="agent-a", sample_size=1, reliability_score=1.0),
                        ],
                    )
                )
            )

        state = _deserialize_mask(response.aggregate_mask)
        self.assertEqual(response.participant_count, 1)
        self.assertAlmostEqual(state["weight"].value, 1.0)


if __name__ == "__main__":
    unittest.main()
