import torch
import os
import sys
import unittest

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from bank_node.privacy_layer.src.privacy_engine import privacy_module
from bank_node.local_gnn_model.src.model import get_model

class TestSecurityAndPrivacy(unittest.TestCase):
    def setUp(self):
        self.model = get_model(input_dim=183, hidden_dim=64, output_dim=3)
        self.state_dict = self.model.state_dict()

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
