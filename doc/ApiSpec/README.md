# REST API And Kafka UI Access

This folder gives you one place to access the live Swagger/OpenAPI docs for the REST services in this project and the Kafka UI dashboard for the messaging layer.

## What Is Here

- `index.html`: browser-friendly page with direct links to Swagger UI and `openapi.json`
- `port-forward-swagger.sh`: common helper script to expose all API services locally from Kubernetes
- `port-forward-kafka-ui.sh`: helper script to expose Kafka UI locally from Kubernetes

## Services With Swagger UI

These services use FastAPI, so Swagger UI is available at `/docs` and OpenAPI JSON is available at `/openapi.json`:

| Service | Kubernetes Service | Local Port |
|---|---|---:|
| Agentic Coordinator | `agentic-coordinator` | 8001 |
| Secure Aggregator | `secure-aggregator` | 8002 |
| Policy Manager | `policy-manager` | 8003 |
| Model Registry | `model-registry` | 8004 |
| Local Agent | `local-agent` | 9001 |
| Local GNN | `local-gnn` | 9002 |
| Privacy Layer | `privacy-layer` | 9003 |
| Transaction Graph | `transaction-graph` | 9004 |
| Alerting | `alerting` | 9005 |

`fraud-dashboard` is the Fraud Dashboard React UI, so it does not expose Swagger.

## How To Run

Run the common script whenever you want Swagger/OpenAPI access:

```bash
bash doc/ApiSpec/port-forward-swagger.sh
```

This starts all required `kubectl port-forward` sessions and keeps them running in that terminal.

If you already started the full stack with:

```bash
bash scripts/all_in_one_minikube.sh up --start-minikube
```

the API endpoints may already be available through the managed port-forwards from that workflow.

To open the central API index in your browser automatically:

```bash
bash doc/ApiSpec/port-forward-swagger.sh --open
```

Then open:

- `doc/ApiSpec/index.html` in your browser
- or click the local Swagger links listed by the script

Or directly use links like:

- [Agentic Coordinator Swagger](http://127.0.0.1:8001/docs)
- [Transaction Graph Swagger](http://127.0.0.1:9004/docs)

## Kafka UI

Run the Kafka UI helper when you want to inspect brokers, topics, partitions, consumer groups, and message data:

```bash
bash doc/ApiSpec/port-forward-kafka-ui.sh
```

To open the Kafka UI dashboard in your browser automatically:

```bash
bash doc/ApiSpec/port-forward-kafka-ui.sh --open
```

Default local Kafka UI URL for `kafka-ui`:

- [Kafka UI](http://127.0.0.1:18080)

If `18080` is already in use on your Mac, the script now automatically tries the next free local port and prints the final URL.

If you started the platform with the all-in-one minikube workflow:

```bash
bash scripts/all_in_one_minikube.sh up --start-minikube
```

Kafka UI is exposed at:

- [Kafka UI via all-in-one](http://127.0.0.1:8080)

## Kafka Inventory Used By This System

The current overall system Kafka setup exposed in the dashboard is:

| Item | Value |
|---|---|
| Cluster | `federated-fraud-kafka` |
| Broker | `kafka:9092` |
| Broker ID | `1` |
| Application Topics | `transactions.events`, `fraud.alerts` |
| Internal Topic | `__consumer_offsets` |

Topic meaning:

- `transactions.events`: produced by `transaction-graph` CDC when transactions are inserted.
- `fraud.alerts`: consumed by `alerting` for alert delivery and recent alert tracking.
- `__consumer_offsets`: Kafka internal topic used by the broker for consumer offset management.

## Important Notes

- Keep the port-forward script running while you use Swagger.
- Keep the Kafka UI port-forward script running while you use the `kafka-ui` dashboard.
- Press `Ctrl+C` in the script terminal to stop all forwarded ports.
- Swagger shows the live request/response schemas from each running FastAPI service.
- If a service is rebuilt or restarted, run the script again so the local forwards are refreshed.
- The all-in-one workflow manages its own port-forwards, so use the URLs printed by `scripts/all_in_one_minikube.sh status` when that stack is already running.
