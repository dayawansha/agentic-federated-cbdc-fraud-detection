"""
Local performance benchmark for the local-gnn-model service.

Measures how large a trained model's state dict is, and how long it takes to
serialize it — the payload local-agent hands off to the privacy-layer before
every federated submission.

Run from the local-gnn-model service directory:
    python benchmarks/performance_test.py
"""
import io
import os
import sys
import time
from pathlib import Path

import psutil
import torch

SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

from model import get_model


def benchmark_model_serialization():
    """
    Builds a default-sized FraudGNN model and measures how large its serialized
    state dict is and how long `torch.save` takes to produce it - this is the
    payload local-agent sends to privacy-layer on every federated round.
    """
    print("\n--- Model Serialization Latency ---")
    model = get_model(input_dim=183, hidden_dim=64, output_dim=3)
    state_dict = model.state_dict()

    buffer = io.BytesIO()
    start_time = time.time()
    torch.save(state_dict, buffer)
    weights_bytes = buffer.getvalue()
    end_time = time.time()

    size_mb = len(weights_bytes) / (1024 * 1024)
    print(f"Model State Dict Size: {size_mb:.2f} MB")
    print(f"Serialization Latency: {(end_time - start_time) * 1000:.2f} ms")


def benchmark_resource_usage():
    """
    Reports the current process's memory (RSS) and CPU usage, giving a rough
    sense of the service's resource footprint while idle/after benchmarking.
    """
    print("\n--- Resource Usage (Process) ---")
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"Memory Usage: {mem_info.rss / (1024 * 1024):.2f} MB")
    print(f"CPU Percent: {process.cpu_percent()}%")


if __name__ == "__main__":
    benchmark_model_serialization()
    benchmark_resource_usage()
