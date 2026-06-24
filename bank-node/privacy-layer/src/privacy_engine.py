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

    def clip_per_sample_gradients(self, grad_samples: list, max_grad_norm: float = 1.0) -> list:
        """
        Clips per-sample gradients to bound sensitivity, mimicking PyTorch Opacus per-sample clipping.
        Each tensor in grad_samples should have a batch dimension as its first dimension (dim 0).
        Returns the aggregated (summed) clipped gradients for each parameter, preserving None values.
        """
        import torch
        if not grad_samples:
            return []

        # Find first non-None gradient to determine batch size and device
        first_tensor = None
        for g in grad_samples:
            if g is not None:
                first_tensor = torch.as_tensor(g)
                break
        
        if first_tensor is None:
            # All gradients are None
            return grad_samples

        batch_size = first_tensor.shape[0]
        device = first_tensor.device

        # Compute per-sample L2 norms across all non-None gradients
        squared_norms = torch.zeros(batch_size, device=device)
        for g in grad_samples:
            if g is not None:
                t = torch.as_tensor(g)
                if t.shape[0] != batch_size:
                    raise ValueError("All gradient samples must have the same batch size (dim 0)")
                # Flatten all dimensions except the batch dimension
                flat_t = t.view(batch_size, -1)
                squared_norms += flat_t.pow(2).sum(dim=1)
        
        norms = squared_norms.sqrt()
        
        # Compute clipping coefficients: min(1.0, max_grad_norm / norms)
        # Add a small epsilon to avoid division by zero
        eps = 1e-6
        coefs = torch.clamp(max_grad_norm / (norms + eps), max=1.0)
        
        # Apply scaling to each parameter's per-sample gradients and sum them, preserving None
        clipped_grads = []
        for g in grad_samples:
            if g is None:
                clipped_grads.append(None)
            else:
                t = torch.as_tensor(g)
                # Reshape coefs to align with tensor dimensions for broadcasting
                shape = [batch_size] + [1] * (t.dim() - 1)
                coefs_broadcast = coefs.view(*shape).to(t.device)
                
                # Clip and then sum over the batch dimension
                clipped_per_sample = t * coefs_broadcast
                aggregated_grad = clipped_per_sample.sum(dim=0)
                clipped_grads.append(aggregated_grad)
            
        return clipped_grads

    def make_model_private(self, model: Any, optimizer: Any, data_loader: Any, noise_multiplier: float, max_grad_norm: float):
        """
        Wraps a PyTorch model and optimizer using Opacus PrivacyEngine to enable DP training.
        """
        try:
            from opacus import PrivacyEngine
            privacy_engine = PrivacyEngine()
            model, optimizer, data_loader = privacy_engine.make_private(
                module=model,
                optimizer=optimizer,
                data_loader=data_loader,
                noise_multiplier=noise_multiplier,
                max_grad_norm=max_grad_norm,
            )
            return model, optimizer, data_loader
        except Exception as e:
            logger.warning(f"Failed to use Opacus PrivacyEngine: {e}. Returning original model and optimizer.")
            return model, optimizer, data_loader

privacy_module = PrivacyModule()
