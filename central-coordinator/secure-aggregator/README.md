# Secure Aggregator

Federated model aggregation with optional DP noise over REST.

## Runtime Name
- `secure-aggregator`

## Responsibilities
- Receive encrypted model updates
- Perform FedAvg/FedProx aggregation
- Apply noise for differential privacy
- Distribute global model

## Technology Stack
- Python 3.11+
- PyTorch
- Flower (FL framework)
- REST + Kafka

## Port
- 8002
