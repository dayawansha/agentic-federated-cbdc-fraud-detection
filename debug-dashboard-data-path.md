# Debug Session: dashboard-data-path

- Status: OPEN
- Started: 2026-06-15
- Goal: drive transaction-graph and alerting data paths until the dashboard shows meaningful live data

## Symptoms
- Dashboard UI is live and service health is green.
- `transaction-graph` health is green, but `/accounts` returns empty data.
- `alerting` health is green, but `/alerts/recent` returns an empty list.
- The federated-learning round path is now working, but it does not itself populate dashboard-visible graph/alert data.

## Initial Hypotheses
- H1: `transaction-graph` has no seeded or ingested transaction/account data in Neo4j, so dashboard analytics stay empty.
- H2: Kafka/CDC production into `transaction-graph` is not being triggered by the current test flow, so graph data never appears.
- H3: `alerting` is healthy but receives no Kafka fraud events, so `/alerts/recent` remains empty.
- H4: Graph or alert events are being produced, but schema mismatches prevent persistence/exposure through the REST endpoints.
- H5: The dashboard proxy path is correct, but the backend services need a focused seed/replay step to generate meaningful data.

## Evidence Log
- `transaction-graph` startup recovered, but `/accounts` returns zero rows and Neo4j warns that `Account`, `Transaction`, `SENDS`, and `RECEIVES` do not exist yet.
- `alerting` starts successfully, but Kafka reports `Unknown topic or partition` for `fraud.alerts`, so no recent alerts can accumulate.
- Existing federated-learning traffic does not populate the graph or alert topics by itself.

## Actions
- Read runtime logs from `transaction-graph` and `alerting`.
- Confirmed the existing processed-data bootstrap script targets `POST /transactions`.
- Patched `alerting` so Kafka topic availability errors do not kill the consumer loop.
- Created the `fraud.alerts` Kafka topic.
- Loaded 40 processed transactions into `transaction-graph` through the public API.
- Published 5 fraud alert events into Kafka and verified they were consumed.
- Verified dashboard proxy routes return non-empty graph and alert payloads.

## Outcome
- H1 CONFIRMED: graph data is absent in Neo4j.
- H2 INCONCLUSIVE: transaction CDC publishing exists, but no evidence yet that it has been triggered in this session.
- H3 CONFIRMED: alert topic/data is absent, so `recent_alerts` remains empty.
- H4 REJECTED for current symptom scope: the immediate problem is missing data/topic availability, not dashboard proxying.
- H5 LIKELY: next step is to seed graph data and publish alert events through the intended runtime paths.
- Post-fix evidence:
  - `GET /accounts?limit=10` returns populated account summaries.
  - `GET /alerts/recent?limit=10` returns 5 recent alerts.
  - Dashboard proxy routes `/api/transaction-graph/accounts` and `/api/alerting/alerts/recent` both return non-empty payloads.
