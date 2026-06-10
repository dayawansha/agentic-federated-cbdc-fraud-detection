import logging
import torch
import io
import asyncio
import grpc
from typing import List

# Placeholder for generated gRPC code
# import federated_pb2
# import federated_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecureAggregator:
    @staticmethod
    def federated_averaging(model_updates: List[bytes], sample_sizes: List[int]) -> bytes:
        """
        Performs Federated Averaging (FedAvg) on a list of model updates.
        Updates are expected to be serialized PyTorch state_dicts.
        """
        if not model_updates:
            return b""
        
        total_samples = sum(sample_sizes)
        # Load the first update as the base
        base_update = torch.load(io.BytesIO(model_updates[0]))
        
        # Initialize the global state dict with zero weights
        global_state = {key: torch.zeros_like(val).float() for key, val in base_update.items()}
        
        # Aggregate weights
        for i, update_bytes in enumerate(model_updates):
            client_state = torch.load(io.BytesIO(update_bytes))
            weight = sample_sizes[i] / total_samples
            
            for key in global_state:
                global_state[key] += client_state[key].float() * weight
        
        # Serialize global state
        buffer = io.BytesIO()
        torch.save(global_state, buffer)
        return buffer.getvalue()

# gRPC Implementation
class SecureAggregatorServicer:
    async def AggregateUpdates(self, request, context):
        logger.info(f"gRPC: Aggregating updates for round {request.round_id}")
        # In a real scenario, this would fetch updates from a buffer or database
        # For now, it's a logic placeholder
        return {"success": True}

async def serve():
    server = grpc.aio.server()
    # federated_pb2_grpc.add_SecureAggregatorServicer_to_server(SecureAggregatorServicer(), server)
    listen_addr = "[::]:8002"
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting Secure Aggregator gRPC server on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
