import torch
import logging
from cryptography.fernet import Fernet
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PrivacyModule:
    def __init__(self, key: bytes = None):
        self.key = key or Fernet.generate_key()
        self.cipher = Fernet(self.key)

    def apply_differential_privacy(self, weights: torch.Tensor, noise_multiplier: float = 0.1):
        """
        Applies Gaussian noise to a tensor to achieve Differential Privacy.
        """
        noise = torch.randn_like(weights) * noise_multiplier
        return weights + noise

    def encrypt_model(self, model_bytes: bytes) -> bytes:
        """
        Encrypts serialized model weights using AES.
        """
        logger.info("Encrypting model weights...")
        return self.cipher.encrypt(model_bytes)

    def decrypt_model(self, encrypted_bytes: bytes) -> bytes:
        """
        Decrypts model weights.
        """
        logger.info("Decrypting model weights...")
        return self.cipher.decrypt(encrypted_bytes)

    def process_weights_for_federation(self, weights_dict: dict, noise_multiplier: float = 0.01) -> dict:
        """
        Applies DP noise to all layers in a state_dict.
        """
        logger.info(f"Applying DP noise with multiplier: {noise_multiplier}")
        private_weights = {}
        for key, val in weights_dict.items():
            if val.is_floating_point():
                private_weights[key] = self.apply_differential_privacy(val, noise_multiplier)
            else:
                private_weights[key] = val
        return private_weights

privacy_module = PrivacyModule()
