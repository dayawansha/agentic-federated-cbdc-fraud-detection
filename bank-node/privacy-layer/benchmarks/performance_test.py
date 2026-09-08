"""
Local performance benchmark for the privacy-layer service.

Measures the latency cost of the privacy pipeline a model update passes
through before leaving a bank node: DP noise injection, then AES transport
encryption/decryption. Uses a synthetic state dict shaped like a small GNN
so this benchmark stays self-contained (no cross-service import of the
actual local-gnn-model).

Run from the privacy-layer service directory:
    python benchmarks/performance_test.py
"""
import os
import sys
import time
from pathlib import Path

import psutil
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


def benchmark_privacy_pipeline():
    print("\n--- Privacy Pipeline Latency ---")
    state_dict = _synthetic_state_dict()

    import io
    buffer = io.BytesIO()
    torch.save(state_dict, buffer)
    weights_bytes = buffer.getvalue()
    print(f"Synthetic State Dict Size: {len(weights_bytes) / (1024 * 1024):.2f} MB")

    # Benchmark DP noise injection
    start_time = time.time()
    private_weights = privacy_module.process_weights_for_federation(state_dict, noise_multiplier=0.01)
    end_time = time.time()
    print(f"DP Noise Injection Latency: {(end_time - start_time) * 1000:.2f} ms")

    # Benchmark AES encryption
    start_time = time.time()
    encrypted_weights = privacy_module.encrypt_model(weights_bytes)
    end_time = time.time()
    print(f"AES Encryption Latency: {(end_time - start_time) * 1000:.2f} ms")

    # Benchmark AES decryption
    start_time = time.time()
    privacy_module.decrypt_model(encrypted_weights)
    end_time = time.time()
    print(f"AES Decryption Latency: {(end_time - start_time) * 1000:.2f} ms")


def benchmark_resource_usage():
    print("\n--- Resource Usage (Process) ---")
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"Memory Usage: {mem_info.rss / (1024 * 1024):.2f} MB")
    print(f"CPU Percent: {process.cpu_percent()}%")


if __name__ == "__main__":
    benchmark_privacy_pipeline()
    benchmark_resource_usage()
