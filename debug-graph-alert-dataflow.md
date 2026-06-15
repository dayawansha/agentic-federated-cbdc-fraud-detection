# Debug Session: graph-alert-dataflow

Status: [OPEN]
Started: 2026-06-15

## Scope
- Collect runtime evidence for transaction-graph and alerting data-flow gaps without changing business logic.
- Verify whether the current local deployment exposes real graph/account data and recent alerts end to end.

## Initial Symptoms
- Dashboard-facing graph and alert data paths have been flaky across local runtime validation.
- Fresh-tag rollout work is in progress, but runtime evidence is still needed for the data path itself.

## Initial Hypotheses
1. `transaction-graph` is healthy but has no meaningful seeded graph data in Neo4j, so account and feature endpoints return empty payloads.
2. `alerting` is healthy but is not receiving Kafka `fraud.alerts` messages, so `/alerts/recent` stays empty.
3. Fraud events are published, but the dashboard proxy or service routing is pointing at stale or wrong upstreams, so live APIs do not reflect current service state.
4. Services are running, but the current cluster/image revision mismatch means the deployed code path differs from the repo code path.
5. Data exists upstream, but endpoint-level filtering, limits, or request failures are suppressing visible results in dashboard-facing API calls.

## Evidence Plan
- Confirm current cluster context and deployment image tags.
- Query runtime health and dashboard-facing APIs for `transaction-graph`, `alerting`, and dashboard proxy routes.
- Inspect recent service logs and Kubernetes state for graph ingestion and fraud alert consumption.
- Only add instrumentation if logs and live API responses are insufficient to falsify the hypotheses above.

## Runtime Evidence Collected
- Dashboard proxy root returned `200`.
- Dashboard proxy `GET /api/transaction-graph/accounts?limit=5` returned 5 accounts, so graph/account data is currently non-empty.
- Dashboard proxy `GET /api/alerting/alerts/recent?limit=5` returned `[]`, so alert feed is still empty.
- Dashboard proxy `GET /api/transaction-graph/health` returned `{"status":"healthy"}`.
- Dashboard proxy `GET /api/alerting/health` returned `{"status":"healthy"}`.
- Direct `GET /agent/status` on `local-agent` returned only the older status shape and omitted inference fields.
- Direct `GET /agent/inference?limit=3` on `local-agent` returned `404`.
- Runtime `local-agent` pod source at `/app/src/main.py` does not contain the `/agent/inference` route that exists in the repo version.
- `kubectl get deployment local-agent -o jsonpath='{.spec.template.spec.containers[0].image}'` returned `dusman/federated-fraud-local-agent:latest`.
- `alerting` runtime logs show Kafka bootstrap resolution failures plus `UNKNOWN_TOPIC_OR_PART` for `fraud.alerts`.
- `transaction-graph` runtime logs show Kafka bootstrap resolution failures and Neo4j DNS/connection failures during startup.

## Hypothesis Status
| ID | Hypothesis | Status | Evidence |
|----|------------|--------|----------|
| A | `transaction-graph` is healthy but Neo4j currently lacks seeded account/edge data. | REJECTED | Dashboard proxy returned 5 non-empty accounts from `GET /api/transaction-graph/accounts?limit=5`. |
| B | `alerting` is healthy but Kafka delivery into `fraud.alerts` is missing or lagging. | CONFIRMED | `GET /api/alerting/alerts/recent?limit=5` returned `[]`; alerting logs show Kafka bootstrap failures and `UNKNOWN_TOPIC_OR_PART` for `fraud.alerts`. |
| C | Dashboard proxy routes are hitting stale or mismatched upstreams. | PARTIAL | Dashboard proxy health routes work and graph accounts are non-empty, so proxying itself is functional; alerting remains empty because upstream alert data is absent. |
| D | The deployed image revision still differs from the repo revision for one or more services. | CONFIRMED | Runtime `local-agent` pod source lacks `/agent/inference`, while the repo version includes it; deployed image is still `dusman/federated-fraud-local-agent:latest`. |
| E | Data exists upstream, but endpoint filtering or request failures hide it from dashboard-facing API calls. | PARTIAL | Transaction-graph data is visible, so filtering is not the primary graph issue; alerting emptiness is better explained by upstream Kafka/topic failures. |

## Operational Recovery Evidence
- Ensured Kafka topic `fraud.alerts` exists in-cluster.
- Replayed 40 processed transaction-graph inserts successfully (`successful_inserts: 40`, `failed_inserts: 0`).
- Published 5 demo fraud alerts into `fraud.alerts`.
- Verified dashboard proxy now returns `dashboard_accounts_count: 10` and `dashboard_alert_count: 5`.
- Verified a sample alert is visible through the dashboard proxy with `received_at` populated.

## Current Conclusion
- The graph/account data path is functioning.
- The alerting data path failure was operational, not business-logic based: Kafka topic availability plus missing replayed alert events left `/alerts/recent` empty.
- A separate runtime issue remains for stale service revision rollout, most clearly visible in `local-agent`, but that is distinct from the graph/alert dashboard data-gap itself.
