import time
import torch
import os
import sys
import psutil
import json
from typing import Dict

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from bank_node.privacy_layer.src.privacy_engine import privacy_module
from bank_node.local_gnn_model.src.model import get_model

def benchmark_model_serialization():
    print("\n--- Model Serialization & Privacy Latency ---")
    model = get_model(input_dim=183, hidden_dim=64, output_dim=3)
    state_dict = model.state_dict()
    
    # Measure serialization size
    import io
    buffer = io.BytesIO()
    start_time = time.time()
    torch.save(state_dict, buffer)
    weights_bytes = buffer.getvalue()
    end_time = time.time()
    
    size_mb = len(weights_bytes) / (1024 * 1024)
    print(f"Model State Dict Size: {size_mb:.2f} MB")
    print(f"Serialization Latency: {(end_time - start_time)*1000:.2f} ms")
    
    # Benchmark Privacy Layer
    start_time = time.time()
    private_weights = privacy_module.process_weights_for_federation(state_dict, noise_multiplier=0.01)
    end_time = time.time()
    print(f"DP Noise Injection Latency: {(end_time - start_time)*1000:.2f} ms")
    
    # Benchmark Encryption
    start_time = time.time()
    encrypted_weights = privacy_module.encrypt_model(weights_bytes)
    end_time = time.time()
    print(f"AES Encryption Latency: {(end_time - start_time)*1000:.2f} ms")
    
    # Benchmark Decryption
    start_time = time.time()
    decrypted_weights = privacy_module.decrypt_model(encrypted_weights)
    end_time = time.time()
    print(f"AES Decryption Latency: {(end_time - start_time)*1000:.2f} ms")

def benchmark_resource_usage():
    print("\n--- Resource Usage (Process) ---")
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"Memory Usage: {mem_info.rss / (1024 * 1024):.2f} MB")
    print(f"CPU Percent: {process.cpu_percent()}%")

if __name__ == "__main__":
    benchmark_model_serialization()
    benchmark_resource_usage()
