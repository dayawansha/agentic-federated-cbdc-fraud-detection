# Secure Aggregator Service

FedAvg/FedGNN model aggregation service.

## Responsibilities
- Receive encrypted model updates
- Perform FedAvg/FedProx aggregation
- Apply noise for differential privacy
- Distribute global model

## Technology Stack
- Python 3.11+
- PyTorch
- Flower (FL framework)
- gRPC

## Port
- 8002
