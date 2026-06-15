import base64
import builtins
import pickle
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SRC = SERVICE_ROOT / "src"

for path in (str(SERVICE_ROOT), str(SERVICE_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

import main


class FakeTorchModule:
    @staticmethod
    def load(buffer):
        return pickle.load(buffer)

    @staticmethod
    def save(obj, buffer):
        pickle.dump(obj, buffer)

    class _TensorVector:
        def __init__(self, values):
            self.values = [float(value) for value in values]

        def is_floating_point(self):
            return True

        def float(self):
            return self

        def flatten(self):
            return self

        def abs(self):
            return FakeTorchModule._TensorVector([abs(value) for value in self.values])

        def pow(self, exponent):
            return FakeTorchModule._TensorVector([value ** exponent for value in self.values])

        def sum(self):
            return FakeTorchModule._Scalar(sum(self.values))

        def max(self):
            return FakeTorchModule._Scalar(max(self.values) if self.values else 0.0)

        def mean(self):
            return FakeTorchModule._Scalar(sum(self.values) / max(1, len(self.values)))

        def __sub__(self, other):
            return FakeTorchModule._TensorVector([left - right for left, right in zip(self.values, other.values)])

        def __add__(self, other):
            return FakeTorchModule._TensorVector([left + right for left, right in zip(self.values, other.values)])

        def __le__(self, other):
            return FakeTorchModule._TensorVector([1.0 if value <= float(other) else 0.0 for value in self.values])

    class _Scalar:
        def __init__(self, value):
            self.value = float(value)

        def item(self):
            return self.value

    class nn:
        class functional:
            @staticmethod
            def cosine_similarity(left, right, _dim=0):
                dot = sum(a * b for a, b in zip(left.values, right.values))
                left_norm = sum(a * a for a in left.values) ** 0.5
                right_norm = sum(b * b for b in right.values) ** 0.5
                if left_norm == 0.0 or right_norm == 0.0:
                    return FakeTorchModule._Scalar(0.0)
                return FakeTorchModule._Scalar(dot / (left_norm * right_norm))

    @staticmethod
    def randn_like(value):
        return FakeTorchModule._TensorVector([0.5 for _ in value.values])

    @staticmethod
    def zeros_like(value):
        return FakeTorchModule._TensorVector([0.0 for _ in value.values])


class TestPrivacyLayer(unittest.IsolatedAsyncioTestCase):
    async def test_apply_dp_returns_original_weights_when_torch_unavailable(self):
        original = base64.b64encode(b"raw-weights").decode("ascii")
        request = main.DPRequest(weights=original, noise_multiplier=0.5)

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("torch missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            response = await main.apply_dp(request)

        self.assertEqual(response.weights, original)

    async def test_apply_dp_uses_privacy_module_when_torch_is_available(self):
        encoded_weights = base64.b64encode(pickle.dumps({"layer": 1.0})).decode("ascii")
        request = main.DPRequest(weights=encoded_weights, noise_multiplier=0.2)

        with patch.dict(sys.modules, {"torch": FakeTorchModule()}):
            with patch.object(
                main.privacy_module,
                "process_weights_for_federation",
                return_value={"layer": 3.5},
            ) as process_mock:
                response = await main.apply_dp(request)

        decoded = pickle.loads(base64.b64decode(response.weights))
        self.assertEqual(decoded, {"layer": 3.5})
        process_mock.assert_called_once_with({"layer": 1.0}, 0.2)

    async def test_encrypt_and_decrypt_round_trip_through_privacy_module(self):
        raw = b"payload-bytes"
        encoded = base64.b64encode(raw).decode("ascii")

        with patch.object(main.privacy_module, "encrypt_model", return_value=b"cipher-text") as encrypt_mock:
            encrypted = await main.encrypt(main.EncryptRequest(data=encoded))

        with patch.object(main.privacy_module, "decrypt_model", return_value=raw) as decrypt_mock:
            decrypted = await main.decrypt(main.DecryptRequest(encrypted_data=encrypted.encrypted_data))

        encrypt_mock.assert_called_once_with(raw)
        decrypt_mock.assert_called_once_with(b"cipher-text")
        self.assertEqual(base64.b64decode(encrypted.encrypted_data), b"cipher-text")
        self.assertEqual(base64.b64decode(decrypted.data), raw)

    async def test_evaluate_privacy_returns_byte_level_metrics_without_tensor_support(self):
        raw = base64.b64encode(b"raw-bytes").decode("ascii")
        protected = base64.b64encode(b"protected-bytes").decode("ascii")
        encrypted = base64.b64encode(b"cipher-bytes").decode("ascii")

        response = await main.evaluate_privacy(
            main.PrivacyEvaluationRequest(
                raw_weights=raw,
                protected_weights=protected,
                encrypted_data=encrypted,
                noise_multiplier=0.1,
            )
        )

        self.assertEqual(response.raw_payload_bytes, len(b"raw-bytes"))
        self.assertEqual(response.protected_payload_bytes, len(b"protected-bytes"))
        self.assertEqual(response.encrypted_payload_bytes, len(b"cipher-bytes"))
        self.assertGreater(response.byte_change_ratio, 0.0)
        self.assertEqual(response.protected_payload_sha256, hashlib.sha256(protected.encode("ascii")).hexdigest())
        self.assertEqual(response.encrypted_payload_sha256, hashlib.sha256(encrypted.encode("ascii")).hexdigest())

    async def test_evaluate_privacy_returns_tensor_level_leakage_proxy_metrics_when_torch_is_available(self):
        raw_state = {"layer": FakeTorchModule._TensorVector([1.0, 2.0, 3.0])}
        protected_state = {"layer": FakeTorchModule._TensorVector([1.0, 2.2, 3.1])}
        request = main.PrivacyEvaluationRequest(
            raw_weights=base64.b64encode(pickle.dumps(raw_state)).decode("ascii"),
            protected_weights=base64.b64encode(pickle.dumps(protected_state)).decode("ascii"),
            encrypted_data="",
            noise_multiplier=0.2,
        )

        with patch.dict(sys.modules, {"torch": FakeTorchModule()}):
            response = await main.evaluate_privacy(request)

        self.assertTrue(response.tensor_metrics_available)
        self.assertGreaterEqual(response.tensor_cosine_similarity, 0.0)
        self.assertGreaterEqual(response.parameter_preservation_ratio, 0.0)
        self.assertIn(response.leakage_risk_level, {"low", "medium", "high"})

    async def test_evaluate_privacy_sweep_runs_multiple_noise_experiments(self):
        with patch.object(main, "apply_dp") as apply_dp_mock, patch.object(main, "encrypt") as encrypt_mock, patch.object(main, "evaluate_privacy") as eval_mock:
            apply_dp_mock.side_effect = [
                main.DPResponse(weights="cDE="),
                main.DPResponse(weights="cDI="),
            ]
            encrypt_mock.side_effect = [
                main.EncryptResponse(encrypted_data="ZTE="),
                main.EncryptResponse(encrypted_data="ZTI="),
            ]
            eval_mock.side_effect = [
                main.PrivacyEvaluationResponse(
                    raw_payload_bytes=1,
                    protected_payload_bytes=1,
                    encrypted_payload_bytes=1,
                    byte_change_ratio=0.5,
                    size_overhead_ratio=1.0,
                    protected_payload_sha256="a" * 64,
                    encrypted_payload_sha256="b" * 64,
                    tensor_l2_delta=0.1,
                    mean_abs_tensor_delta=0.1,
                    max_abs_tensor_delta=0.1,
                    tensor_change_ratio=1.0,
                    tensor_cosine_similarity=0.9,
                    parameter_preservation_ratio=0.2,
                    leakage_proxy_score=0.55,
                    leakage_risk_level="low",
                    tensor_metrics_available=True,
                    noise_multiplier=0.01,
                ),
                main.PrivacyEvaluationResponse(
                    raw_payload_bytes=1,
                    protected_payload_bytes=1,
                    encrypted_payload_bytes=1,
                    byte_change_ratio=0.8,
                    size_overhead_ratio=1.0,
                    protected_payload_sha256="c" * 64,
                    encrypted_payload_sha256="d" * 64,
                    tensor_l2_delta=0.2,
                    mean_abs_tensor_delta=0.2,
                    max_abs_tensor_delta=0.2,
                    tensor_change_ratio=1.0,
                    tensor_cosine_similarity=0.6,
                    parameter_preservation_ratio=0.1,
                    leakage_proxy_score=0.35,
                    leakage_risk_level="low",
                    tensor_metrics_available=True,
                    noise_multiplier=0.1,
                ),
            ]

            response = await main.evaluate_privacy_sweep(
                main.PrivacySweepRequest(raw_weights="cmF3", noise_multipliers=[0.01, 0.1], encrypt_payloads=True)
            )

        self.assertEqual(response.experiment_count, 2)
        self.assertEqual(len(response.results), 2)

    async def test_prepare_secure_update_returns_masked_weights_and_encrypted_mask_share(self):
        protected_state = {"layer": FakeTorchModule._TensorVector([1.0, 2.0])}
        request = main.SecureAggregationPrepareRequest(
            weights=base64.b64encode(pickle.dumps(protected_state)).decode("ascii")
        )

        with patch.dict(sys.modules, {"torch": FakeTorchModule()}):
            response = await main.prepare_secure_update(request)

        masked_state = pickle.loads(base64.b64decode(response.masked_weights))
        self.assertIn("layer", masked_state)
        self.assertNotEqual(response.encrypted_mask_share, "")


if __name__ == "__main__":
    unittest.main()
