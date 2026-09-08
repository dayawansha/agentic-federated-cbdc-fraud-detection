# Debug Session: dashboard-graph-alert-dataflow

- Status: RESOLVED (operational data-path); see Follow-up for a separate unresolved finding
- Started: 2026-06-15
- Merged from: `debug-dashboard-data-path.md` and `debug-graph-alert-dataflow.md` (two sessions investigating the same symptom on the same day; merged here to avoid duplicate history)
- Goal: drive `transaction-graph` and `alerting` data paths until the dashboard shows meaningful live data

## Symptoms

- Dashboard UI is live and service health is green.
- `transaction-graph` health is green, but `/accounts` returns empty data.
- `alerting` health is green, but `/alerts/recent` returns an empty list.
- The federated-learning round path works end to end, but it does not itself populate dashboard-visible graph/alert data.

## Hypotheses

1. `transaction-graph` is healthy but has no meaningful seeded graph data in Neo4j, so account/feature endpoints return empty payloads.
2. Kafka/CDC production into `transaction-graph` is not being triggered by the current test flow, so graph data never appears.
3. `alerting` is healthy but is not receiving Kafka `fraud.alerts` messages, so `/alerts/recent` stays empty.
4. Fraud events are published, but the dashboard proxy or service routing is pointing at stale/wrong upstreams.
5. Services are running, but the deployed cluster/image revision differs from the repo code path.
6. Data exists upstream, but endpoint-level filtering, limits, or request failures suppress visible results in dashboard-facing API calls.

## Evidence Log

- `transaction-graph` startup recovered, but `/accounts` returned zero rows; Neo4j warned that `Account`, `Transaction`, `SENDS`, and `RECEIVES` did not exist yet.
- `alerting` started successfully, but Kafka reported `Unknown topic or partition` / `UNKNOWN_TOPIC_OR_PART` for `fraud.alerts`, so no recent alerts accumulated.
- Existing federated-learning traffic did not populate the graph or alert topics by itself.
- Dashboard proxy root and health routes (`/api/transaction-graph/health`, `/api/alerting/health`) all returned `200` / `{"status":"healthy"}` — proxying itself was functional.
- Dashboard proxy `GET /api/transaction-graph/accounts?limit=5` returned 5 accounts once graph data existed, confirming the graph data path works once seeded.
- Dashboard proxy `GET /api/alerting/alerts/recent?limit=5` returned `[]` until alert events were actually published.
- Direct `GET /agent/status` on `local-agent` returned only an older status shape and omitted inference fields; direct `GET /agent/inference?limit=3` returned `404`.
- Runtime `local-agent` pod source at `/app/src/main.py` did not contain the `/agent/inference` route that exists in the repo version.
- `kubectl get deployment local-agent -o jsonpath='{.spec.template.spec.containers[0].image}'` returned `dusman/federated-fraud-local-agent:latest` — i.e. the running pod was on a stale image tag, not the current repo revision.

## Hypothesis Status

| ID | Hypothesis | Status | Evidence |
|----|------------|--------|----------|
| 1 | Transaction-graph has no seeded data | CONFIRMED (until seeded) | Zero rows from `/accounts`; Neo4j warned target labels didn't exist. Resolved once processed transactions were loaded. |
| 2 | Kafka/CDC not triggered by test flow | INCONCLUSIVE | CDC publish path exists in code, but no evidence it fired in this session. |
| 3 | Alerting not receiving `fraud.alerts` | CONFIRMED | `/alerts/recent` empty; alerting logs showed Kafka bootstrap failures and `UNKNOWN_TOPIC_OR_PART` for `fraud.alerts`. |
| 4 | Dashboard proxy hitting stale/wrong upstreams | REJECTED | Proxy health/routing worked correctly; the emptiness traced to missing upstream data, not proxy misconfiguration. |
| 5 | Deployed image revision differs from repo revision | CONFIRMED (separate finding) | `local-agent` pod ran `:latest` and was missing the `/agent/inference` route present in the repo. |
| 6 | Endpoint filtering/request failures hide existing data | REJECTED for graph data | Once seeded, `/accounts` returned data cleanly with no filtering issues. |

## Actions / Fix Log

- Read runtime logs from `transaction-graph` and `alerting`.
- Confirmed the existing processed-data bootstrap script targets `POST /transactions`.
- **Patched `alerting`** so Kafka topic-availability errors do not kill the consumer loop.
- Created the `fraud.alerts` Kafka topic.
- Loaded 40 processed transactions into `transaction-graph` through the public API (`successful_inserts: 40`, `failed_inserts: 0`).
- Published 5 fraud alert events into Kafka and verified they were consumed.
- Verified dashboard proxy routes return non-empty graph and alert payloads.

## Outcome

- The graph/account data path works correctly once Neo4j is seeded.
- The alerting data path failure was operational, not business-logic based: missing Kafka topic plus no replayed alert events left `/alerts/recent` empty. Both are fixed by topic creation + demo-data seeding (see `scripts/demo_dashboard_lifecycle.sh`).
- Dashboard proxy verified: `dashboard_accounts_count: 10`, `dashboard_alert_count: 5`, sample alert visible with `received_at` populated.

## Follow-up (unresolved at time of writing)

A **separate** issue surfaced during this investigation: the deployed `local-agent` pod was running a stale `:latest` image lacking the `/agent/inference` route present in the repo. This is a rollout/image-tagging issue, not a graph/alert data-flow issue — see the `local_minikube_release.sh` / `all_in_one_minikube.sh` unique-tag workflow in the repo root `README.md`, which was introduced specifically to avoid `:latest`-tag staleness like this.
