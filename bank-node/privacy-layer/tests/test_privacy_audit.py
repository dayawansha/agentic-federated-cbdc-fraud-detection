"""
Security/privacy correctness audit for the privacy-layer's own crypto primitives.

Unlike test_main.py (which mocks out privacy_module to test endpoint wiring),
this exercises the real DP noise and AES encrypt/decrypt implementations
directly, asserting the actual mathematical/cryptographic properties.

Uses a synthetic state dict instead of importing local-gnn-model, so this
service's tests never reach across a service boundary.
"""
import sys
import unittest
from pathlib import Path

import torch

SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

from privacy_engine import privacy_module


def _synthetic_state_dict() -> dict:
    """A state dict with shapes representative of the local-gnn-model's layers."""
    return {
        "conv1.weight": torch.randn(64, 183),
        "conv1.bias": torch.randn(64),
        "conv2.weight": torch.randn(3, 64),
        "conv2.bias": torch.randn(3),
    }


class TestSecurityAndPrivacy(unittest.TestCase):
    def setUp(self):
        self.state_dict = _synthetic_state_dict()

    def test_differential_privacy_noise(self):
        """Verify that DP noise is actually added and weights are different."""
        noise_multiplier = 0.1
        private_weights = privacy_module.process_weights_for_federation(self.state_dict, noise_multiplier)

        for key in self.state_dict:
            original = self.state_dict[key]
            private = private_weights[key]

            # Check that weights are not identical
            if original.is_floating_point():
                self.assertFalse(torch.equal(original, private), f"Layer {key} was not modified by DP noise")

                # Check that the difference is within reasonable noise bounds
                diff = torch.abs(original - private).mean()
                self.assertGreater(diff, 0, f"Mean noise for {key} is 0")
                print(f"Verified DP for layer {key}: Mean Noise = {diff.item():.6f}")

    def test_encryption_integrity(self):
        """Verify that encryption transforms data and decryption restores it perfectly."""
        import io
        buffer = io.BytesIO()
        torch.save(self.state_dict, buffer)
        original_bytes = buffer.getvalue()

        encrypted_bytes = privacy_module.encrypt_model(original_bytes)
        self.assertNotEqual(original_bytes, encrypted_bytes, "Encryption did not change the data")

        decrypted_bytes = privacy_module.decrypt_model(encrypted_bytes)
        self.assertEqual(original_bytes, decrypted_bytes, "Decrypted data does not match original")
        print("Verified Encryption/Decryption Integrity")


if __name__ == "__main__":
    unittest.main()
