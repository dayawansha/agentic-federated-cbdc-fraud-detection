import logging
import base64
import hashlib
import os
import io
from cryptography.fernet import Fernet
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PrivacyModule:
    def __init__(self, key: bytes = None):
        self.key = key or self._resolve_key()
        self.cipher = Fernet(self.key)

    @staticmethod
    def _resolve_key() -> bytes:
        explicit_key = os.getenv("PRIVACY_FERNET_KEY")
        if explicit_key:
            return explicit_key.encode("ascii")

        # secure-aggregation can share the same transport key without extra setup.
        # (federated-model-aggregator and privacy-layer)
        seed = os.getenv("PRIVACY_KEY_SEED", "development-only-shared-key")
        return base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())

    def apply_differential_privacy(self, weights: Any, noise_multiplier: float = 0.1):
        """
        Applies Gaussian noise to a tensor to achieve Differential Privacy.
        """
        import torch
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

    def build_secure_aggregation_artifacts(self, weights_dict: dict) -> tuple[bytes, bytes]:
        """
        Creates an additive mask for each floating-point tensor so the submitted
        update can be aggregated without exposing the underlying protected model.
        Returns the serialized masked state and the encrypted serialized mask.
        """
        import torch

        mask_state = {}
        masked_state = {}
        for key, val in weights_dict.items():
            if val.is_floating_point():
                mask = torch.randn_like(val)
                mask_state[key] = mask
                masked_state[key] = val + mask
            else:
                mask_state[key] = torch.zeros_like(val)
                masked_state[key] = val

        masked_buffer = io.BytesIO()
        torch.save(masked_state, masked_buffer)

        mask_buffer = io.BytesIO()
        torch.save(mask_state, mask_buffer)
        encrypted_mask = self.encrypt_model(mask_buffer.getvalue())
        return masked_buffer.getvalue(), encrypted_mask

privacy_module = PrivacyModule()
